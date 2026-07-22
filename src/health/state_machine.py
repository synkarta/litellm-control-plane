import logging
from datetime import datetime, timedelta, timezone
import sqlite3
from typing import Optional
from src.registry import store
from src.registry.models import Account, Endpoint

logger = logging.getLogger("state_machine")

# Default cooldown duration in seconds
COOLDOWN_DURATION_SEC = 30
FAILURE_THRESHOLD = 3

def transition_account_state(
    conn: sqlite3.Connection,
    account_id: str,
    next_state: str,
    actor: str,
    reason: Optional[str] = None,
    raw_response: Optional[str] = None,
) -> Optional[Account]:
    """
    Perform a clean transition of an account's state, logging and auditing the event.
    """
    acc = store.get_account(conn, account_id)
    if not acc:
        logger.warning(f"Attempted to transition non-existent account: {account_id}")
        return None

    old_state = acc.status
    if old_state == next_state:
        return acc

    # Key Logging Format Requirement
    msg = f"[Account] [{account_id}] State Transition: {old_state} -> {next_state} (Reason: {reason or 'N/A'})"
    logger.info(msg)
    print(msg)  # Explicit stdout logging

    # Record in incidents table
    store.create_incident(conn, "account", account_id, old_state, next_state, reason, raw_response)

    # Perform DB Update
    if next_state == "cooldown":
        cooldown_until = (datetime.now(timezone.utc) + timedelta(seconds=COOLDOWN_DURATION_SEC)).isoformat()
        store.set_account_cooldown(conn, account_id, cooldown_until, actor=actor, reason=reason)
        # set_account_cooldown writes its own audit; skip duplicate below
        return store.get_account(conn, account_id)

    return store.update_account_status(conn, account_id, next_state, actor=actor, reason=reason)

def transition_endpoint_state(
    conn: sqlite3.Connection,
    endpoint_id: str,
    next_state: str,
    actor: str,
    reason: Optional[str] = None,
    raw_response: Optional[str] = None,
) -> Optional[Endpoint]:
    """
    Perform a clean transition of an endpoint's state, logging and auditing the event.
    """
    ep = store.get_endpoint(conn, endpoint_id)
    if not ep:
        logger.warning(f"Attempted to transition non-existent endpoint: {endpoint_id}")
        return None

    old_state = ep.status
    if old_state == next_state:
        return ep

    # Key Logging Format Requirement
    msg = f"[Endpoint] [{endpoint_id}] State Transition: {old_state} -> {next_state} (Reason: {reason or 'N/A'})"
    logger.info(msg)
    print(msg)  # Explicit stdout logging

    # Record in incidents table
    store.create_incident(conn, "endpoint", endpoint_id, old_state, next_state, reason, raw_response)

    # Perform DB Update
    if next_state == "cooldown":
        cooldown_until = (datetime.now(timezone.utc) + timedelta(seconds=COOLDOWN_DURATION_SEC)).isoformat()
        store.set_endpoint_cooldown(conn, endpoint_id, cooldown_until, actor=actor, reason=reason)
        # set_endpoint_cooldown writes its own audit; skip duplicate below
        return store.get_endpoint(conn, endpoint_id)

    return store.update_endpoint_status(conn, endpoint_id, status=next_state, manual_override=None, actor=actor, reason=reason)

def is_auth_error(error_code: int, error_message: str) -> bool:
    """
    Determine if an error is authentication-related based on code or message content.
    """
    msg_lower = error_message.lower()
    return error_code in (401, 403) or "auth" in msg_lower or "api key" in msg_lower

def handle_account_failure(
    conn: sqlite3.Connection,
    account_id: str,
    error_code: int,
    error_message: str,
    actor: str,
    raw_response: Optional[str] = None,
) -> None:
    """
    Classify error and trigger appropriate state transitions for an account.
    """
    if is_auth_error(error_code, error_message):
        transition_account_state(conn, account_id, "disabled", actor,
                                 f"Auth Error ({error_code}): {error_message}", raw_response)
    elif error_code == 429 or "429" in error_message or "rate limit" in error_message.lower():
        transition_account_state(conn, account_id, "cooldown", actor,
                                 f"Rate Limit (429): {error_message}", raw_response)
    else:
        failures = store.increment_account_failure(conn, account_id)
        if failures >= FAILURE_THRESHOLD:
            transition_account_state(
                conn, account_id, "degraded", actor,
                f"Elevated failure count ({failures}): Last error: {error_message}",
                raw_response
            )

def handle_endpoint_failure(
    conn: sqlite3.Connection,
    endpoint_id: str,
    error_code: int,
    error_message: str,
    actor: str,
    raw_response: Optional[str] = None,
) -> None:
    """
    Classify error and trigger appropriate state transitions for an endpoint.
    """
    if is_auth_error(error_code, error_message):
        transition_endpoint_state(conn, endpoint_id, "disabled", actor,
                                  f"Auth Error ({error_code}): {error_message}", raw_response)
    elif error_code == 429 or "429" in error_message or "rate limit" in error_message.lower():
        transition_endpoint_state(conn, endpoint_id, "cooldown", actor,
                                  f"Rate Limit (429): {error_message}", raw_response)
    else:
        failures = store.increment_endpoint_failure(conn, endpoint_id)
        if failures >= FAILURE_THRESHOLD:
            transition_endpoint_state(
                conn, endpoint_id, "degraded", actor,
                f"Elevated failure count ({failures}): Last error: {error_message}",
                raw_response
            )

def handle_account_success(conn: sqlite3.Connection, account_id: str, actor: str) -> None:
    """
    Reset failure state on a success signal.

    Cooldown is time-locked: only reconcile_cooldowns + probe may exit it.
    A success callback can reset degraded/probe/recovered → active, but must
    NOT short-circuit a cooldown timer.
    """
    acc = store.get_account(conn, account_id)
    if not acc:
        return

    if acc.status == "probe":
        if actor == "probe":
            transition_account_state(conn, account_id, "active", actor, "Probe success")
        else:
            logger.debug(f"Ignored straggler success callback for account {account_id} currently in probe state.")
    elif acc.status in ("degraded", "recovered"):
        transition_account_state(conn, account_id, "active", actor, "Success signal received")
    elif acc.status == "active" and acc.failure_count > 0:
        conn.execute("UPDATE accounts SET failure_count = 0 WHERE id = ?", (account_id,))

def handle_endpoint_success(conn: sqlite3.Connection, endpoint_id: str, actor: str) -> None:
    """
    Reset failure state on a success signal.

    Cooldown is time-locked: only reconcile_cooldowns + probe may exit it.
    A success callback can reset degraded/probe/recovered → active, but must
    NOT short-circuit a cooldown timer.
    """
    ep = store.get_endpoint(conn, endpoint_id)
    if not ep:
        return

    if ep.status == "probe":
        if actor == "probe":
            transition_endpoint_state(conn, endpoint_id, "active", actor, "Probe success")
        else:
            logger.debug(f"Ignored straggler success callback for endpoint {endpoint_id} currently in probe state.")
    elif ep.status in ("degraded", "recovered"):
        transition_endpoint_state(conn, endpoint_id, "active", actor, "Success signal received")
    elif ep.status == "active" and ep.failure_count > 0:
        conn.execute("UPDATE endpoints SET failure_count = 0 WHERE id = ?", (endpoint_id,))

