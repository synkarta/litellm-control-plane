import json
import logging
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status
from src.config.db import get_db_dep
from src.health.state_machine import (
    handle_account_failure,
    handle_endpoint_failure,
    handle_account_success,
    handle_endpoint_success,
    is_auth_error
)

logger = logging.getLogger("event_ingestion")
router = APIRouter()

def extract_raw_response(item: Dict[str, Any]) -> Optional[str]:
    """
    Serialize the raw error/exception block from a callback item as a JSON string.
    This is stored in incidents.raw_response so operators can inspect the original
    provider error payload without losing detail.
    """
    raw = item.get("error") or item.get("exception")
    if raw is None:
        return None
    try:
        if isinstance(raw, dict):
            return json.dumps(raw, ensure_ascii=False)
        return str(raw)
    except Exception:
        return str(raw)

def classify_error(item: Dict[str, Any]) -> tuple[int, str]:
    """
    Helper to extract error status code and error message from LiteLLM callback items.
    """
    error_code = 500
    error_msg = "Unknown error"

    # Extract error block
    error_obj = item.get("error") or item.get("exception")
    if error_obj:
        if isinstance(error_obj, dict):
            error_msg = error_obj.get("message") or error_obj.get("message") or str(error_obj)
            # Try to get status code
            code = error_obj.get("status_code") or error_obj.get("code")
            if code:
                try:
                    error_code = int(code)
                except ValueError:
                    pass
        else:
            error_msg = str(error_obj)
    
    # Check exception class or general message strings
    exception_class = item.get("exception_class") or ""
    if "RateLimit" in exception_class or "429" in error_msg or "rate limit" in error_msg.lower():
        error_code = 429
    elif "Authentication" in exception_class or "401" in error_msg or "403" in error_msg or "api key" in error_msg.lower():
        error_code = 401
    elif "Timeout" in exception_class or "timeout" in error_msg.lower():
        error_code = 504

    return error_code, error_msg

@router.post("/events/callback", tags=["events"])
def ingest_event_callback(
    payload: Union[List[Dict[str, Any]], Dict[str, Any]],
    conn = Depends(get_db_dep)
):
    """
    Webhook callback endpoint to ingest standard logging payloads from LiteLLM proxy nodes.
    """
    # Normalize to list
    items = payload if isinstance(payload, list) else [payload]
    
    processed_count = 0
    for item in items:
        # Extract metadata
        meta = item.get("metadata") or {}
        endpoint_id = meta.get("endpoint_id")
        account_id = meta.get("account_id")
        
        # If no custom metadata, try litellm_params metadata
        if not endpoint_id or not account_id:
            litellm_params = item.get("litellm_params") or {}
            params_meta = litellm_params.get("metadata") or {}
            endpoint_id = endpoint_id or params_meta.get("endpoint_id")
            account_id = account_id or params_meta.get("account_id")

        if not endpoint_id and not account_id:
            logger.debug("Callback item skipped: no endpoint_id or account_id metadata found.")
            continue

        # Check if failed or success
        is_failure = "error" in item or "exception" in item or item.get("status") == "failed"

        if is_failure:
            error_code, error_msg = classify_error(item)
            raw_response = extract_raw_response(item)
            logger.warning(
                f"Ingested failure event: endpoint={endpoint_id}, account={account_id}, "
                f"code={error_code}, msg={error_msg}"
            )

            # Scope the failure to the right layer based on error type:
            #
            # - Auth errors (401/403): the credential itself is bad → account-scoped.
            #   Disable both the endpoint and the account so all endpoints under
            #   this account stop being routed until an operator resets the key.
            #
            # - Rate limit (429) / 5xx / timeout: transient or endpoint-specific.
            #   Only touch the endpoint. The account key is still valid; a different
            #   endpoint or model may succeed. Do NOT cascade to account state.
            #
            # - No endpoint context: fall back to account-level handling so we don't
            #   silently drop events that only carry account metadata.

            auth_failed = is_auth_error(error_code, error_msg)

            if endpoint_id:
                handle_endpoint_failure(conn, endpoint_id, error_code, error_msg,
                                        actor="callback-ingest", raw_response=raw_response)

            if account_id:
                if auth_failed:
                    handle_account_failure(conn, account_id, error_code, error_msg,
                                          actor="callback-ingest", raw_response=raw_response)
                elif not endpoint_id:
                    handle_account_failure(conn, account_id, error_code, error_msg,
                                          actor="callback-ingest", raw_response=raw_response)

        else:
            logger.info(f"Ingested success event: endpoint={endpoint_id}, account={account_id}")
            if endpoint_id:
                handle_endpoint_success(conn, endpoint_id, actor="callback-ingest")
            if account_id:
                handle_account_success(conn, account_id, actor="callback-ingest")

        processed_count += 1

    return {"detail": f"Processed {processed_count} events"}

