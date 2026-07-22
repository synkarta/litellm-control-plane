import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional
import yaml
from src.secrets.doppler import DopplerResolver
from src.registry import store

logger = logging.getLogger("config_generator")

# Provider types that are cloud-hosted and never need an api_base
_CLOUD_PROVIDER_TYPES = frozenset({"openai", "anthropic", "gemini", "cohere", "mistral", "azure"})

# Provider-specific model string prefixes
_NIM_PREFIX = "openai"

class ConfigGenerator:
    def __init__(self, resolver: DopplerResolver):
        self.resolver = resolver

    def generate_config(self, conn: sqlite3.Connection, node_id: str) -> Dict[str, Any]:
        """
        Compile configuration for a specific LiteLLM Node.
        """
        cursor = conn.execute(
            """
            SELECT
                e.id as ep_id, e.priority, e.weight, e.status as ep_status, e.manual_override,
                m.id as model_id, m.name as model_name, m.logical_group,
                a.id as acc_id, a.secret_ref, a.status as acc_status,
                p.id as prov_id, p.type as prov_type
            FROM endpoints e
            JOIN models m ON e.model_id = m.id
            JOIN accounts a ON e.account_id = a.id
            JOIN providers p ON a.provider_id = p.id
            WHERE e.node_id = ?
            """,
            (node_id,)
        )
        rows = cursor.fetchall()

        model_list = []
        for r in rows:
            prov_type = r["prov_type"].lower()
            manual_override = r["manual_override"]
            ep_status = r["ep_status"]
            acc_status = r["acc_status"]

            # M2 fix: warn when force-active intent is blocked by account status
            if manual_override == "force-active" and acc_status in ("disabled", "inactive"):
                logger.warning(
                    f"Endpoint {r['ep_id']} has manual_override=force-active but its account "
                    f"({r['acc_id']}) has status='{acc_status}'. Endpoint will be excluded."
                )

            # Apply exclusion filters
            if manual_override == "force-disabled":
                continue

            if manual_override != "force-active":
                if ep_status in ("disabled", "cooldown", "degraded"):
                    continue
                if acc_status in ("disabled", "inactive", "cooldown"):
                    continue
            else:
                # force-active endpoints are still excluded if their account is disabled or inactive
                if acc_status in ("disabled", "inactive"):
                    continue

            # Resolve secret
            secret_ref = r["secret_ref"]
            try:
                api_key = self.resolver.resolve(secret_ref)
            except Exception as e:
                logger.warning(
                    f"Skipping endpoint {r['ep_id']} due to secret resolution failure: {e}"
                )
                continue

            # Formulate upstream model string
            model_string = r["model_name"]
            if prov_type == "nim":
                model_string = f"{_NIM_PREFIX}/{r['model_name']}"
            elif prov_type not in _CLOUD_PROVIDER_TYPES:
                model_string = f"{prov_type}/{r['model_name']}"

            litellm_params: Dict[str, Any] = {
                "model": model_string,
                "api_key": api_key,
                "order": r["priority"],
                "weight": r["weight"]
            }

            # Resolve API Base for any self-hosted provider type (H3 fix: not just ollama/nim)
            if prov_type not in _CLOUD_PROVIDER_TYPES:
                api_base = self._resolve_api_base(r, prov_type, secret_ref)
                if api_base:
                    # Sanitize Ollama api_base: strip /api or /api/ suffix
                    if prov_type == "ollama":
                        api_base = api_base.rstrip("/")
                        if api_base.endswith("/api"):
                            api_base = api_base[:-4]
                    litellm_params["api_base"] = api_base

            # Apply force-active manual override: push to front of routing queue
            if manual_override == "force-active":
                litellm_params["order"] = 1

            model_list.append({
                "model_name": r["logical_group"],
                "litellm_params": litellm_params
            })

        return {
            "model_list": model_list,
            "litellm_settings": {
                "drop_params": True
            }
        }

    def _resolve_api_base(self, row: Any, prov_type: str, secret_ref: str) -> Optional[str]:
        """
        Try to resolve api_base for a self-hosted provider endpoint.
        Resolution order:
          1. Doppler secrets: <PROVIDER_ID>_API_BASE
          2. Doppler secrets: <PROVIDER_TYPE>_API_BASE
          3. Local OS env: <PROVIDER_ID>_API_BASE
          4. Local OS env: <PROVIDER_TYPE>_API_BASE
        """
        prov_id_key = f"{row['prov_id'].upper()}_API_BASE"
        prov_type_key = f"{prov_type.upper()}_API_BASE"

        # Try Doppler first
        try:
            project, config, _ = self.resolver.parse_uri(secret_ref)
            token = self.resolver._get_token(project, config)
            if token:
                secrets = self.resolver._get_secrets_with_cache(token)
                if prov_id_key in secrets:
                    return secrets[prov_id_key]
                if prov_type_key in secrets:
                    return secrets[prov_type_key]
        except Exception:
            pass

        # Fallback to local OS env
        return os.getenv(prov_id_key) or os.getenv(prov_type_key)

    def write_config_to_file(self, config: Dict[str, Any], filepath: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False)
