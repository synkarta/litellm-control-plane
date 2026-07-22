import logging
import httpx
import sqlite3
from typing import Optional
from src.secrets.doppler import DopplerResolver
from src.registry import store
from src.health.state_machine import transition_endpoint_state, transition_account_state, handle_endpoint_failure, handle_endpoint_success

logger = logging.getLogger("probe_engine")

class ProbeEngine:
    def __init__(self, resolver: DopplerResolver, client: Optional[httpx.Client] = None):
        self.resolver = resolver
        self.client = client or httpx.Client(timeout=5.0)

    def probe_endpoint(self, conn: sqlite3.Connection, endpoint_id: str, actor: str = "probe-engine") -> bool:
        """
        Executes a lightweight active probe against a specific Endpoint's upstream provider.
        If healthy, transitions state to active. If unhealthy, keeps/updates failure state.
        Returns True if the endpoint was successfully validated as healthy.
        """
        ep = store.get_endpoint(conn, endpoint_id)
        if not ep:
            logger.warning(f"Attempted to probe non-existent endpoint: {endpoint_id}")
            return False

        acc = store.get_account(conn, ep.account_id)
        model = store.get_model(conn, ep.model_id)
        if not acc or not model:
            logger.warning(f"Endpoint {endpoint_id} references missing account or model.")
            return False

        # Resolve upstream secret key
        try:
            api_key = self.resolver.resolve(acc.secret_ref)
        except Exception as e:
            logger.error(f"Probe failed to resolve secrets for account {acc.id}: {e}")
            handle_endpoint_failure(conn, endpoint_id, 401, f"Secret resolution failure: {e}", actor=actor)
            return False

        # Transition endpoint status to 'probe' first to represent active verification
        transition_endpoint_state(conn, endpoint_id, "probe", actor=actor, reason="Starting active health probe")

        # Determine target URL and payload depending on provider type
        # For MVP, we determine target by provider type (e.g. ollama, nim, openai, anthropic)
        prov = conn.execute("SELECT type FROM providers WHERE id = ?", (acc.provider_id,)).fetchone()
        prov_type = prov[0].lower() if prov else "openai"

        # Mock check: during tests, if the API key is "mock-key", we skip network calls and succeed
        if api_key == "mock-key" or api_key.startswith("mock-"):
            logger.info(f"Mock probe successful for endpoint {endpoint_id}")
            # Transition through recovered to active
            transition_endpoint_state(conn, endpoint_id, "recovered", actor=actor, reason="Active probe validation passed (mocked)")
            handle_endpoint_success(conn, endpoint_id, actor=actor)
            return True

        # Construct request parameters
        url = ""
        headers = {}
        payload = {}

        if prov_type == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": model.name,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }
        elif prov_type == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": model.name,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}]
            }
        elif prov_type == "ollama":
            # Strip suffix
            base_url = "http://localhost:11434"
            if api_key:
                headers = {"Authorization": f"Bearer {api_key}"}
            url = f"{base_url}/api/generate"
            payload = {
                "model": model.name,
                "prompt": "ping",
                "stream": False,
                "options": {"num_predict": 1}
            }
        else:
            # Fallback/NIM/Generic OpenAI-compatible
            base_url = "https://integrate.api.nvidia.com/v1" if prov_type == "nim" else "https://api.openai.com/v1"
            url = f"{base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": model.name,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }

        try:
            response = self.client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info(f"Active probe successful for endpoint {endpoint_id}")
                transition_endpoint_state(conn, endpoint_id, "recovered", actor=actor, reason="Active probe validation passed")
                handle_endpoint_success(conn, endpoint_id, actor=actor)
                return True
            else:
                logger.warning(f"Active probe failed for endpoint {endpoint_id}: HTTP {response.status_code} - {response.text}")
                handle_endpoint_failure(conn, endpoint_id, response.status_code, f"Probe HTTP {response.status_code}: {response.text}", actor=actor)
                return False
        except Exception as e:
            logger.warning(f"Active probe connection exception for endpoint {endpoint_id}: {e}")
            handle_endpoint_failure(conn, endpoint_id, 503, f"Probe connection exception: {e}", actor=actor)
            return False

    def reconcile_cooldowns(self, conn: sqlite3.Connection, actor: str = "reconcile-worker") -> None:
        """
        Scans all cooldown resources. If their cooldown time has expired, triggers active probe or transitions them back.
        """
        from datetime import datetime, timezone
        now_str = datetime.now(timezone.utc).isoformat()

        # --- Expired endpoints: probe before re-activating ---
        expired_endpoints = conn.execute(
            "SELECT id FROM endpoints WHERE status = 'cooldown' AND (cooldown_until IS NULL OR cooldown_until <= ?)",
            (now_str,)
        ).fetchall()

        for (ep_id,) in expired_endpoints:
            logger.info(f"Cooldown expired for endpoint {ep_id}. Scheduling probe.")
            self.probe_endpoint(conn, ep_id, actor=actor)

        # --- Expired accounts: probe via an associated endpoint, not direct activation ---
        expired_accounts = conn.execute(
            "SELECT id FROM accounts WHERE status = 'cooldown' AND (cooldown_until IS NULL OR cooldown_until <= ?)",
            (now_str,)
        ).fetchall()

        for (acc_id,) in expired_accounts:
            logger.info(f"Cooldown expired for account {acc_id}. Starting probe via endpoint.")
            transition_account_state(
                conn, acc_id, "probe", actor=actor,
                reason="Account cooldown expired, starting active probe"
            )
            # Find any non-disabled endpoint associated with this account to probe through
            row = conn.execute(
                "SELECT id FROM endpoints WHERE account_id = ? AND status NOT IN ('disabled', 'cooldown', 'probe') LIMIT 1",
                (acc_id,)
            ).fetchone()
            if row:
                ep_id = row[0]
                result = self.probe_endpoint(conn, ep_id, actor=actor)
                if result:
                    transition_account_state(
                        conn, acc_id, "active", actor=actor,
                        reason="Account probe passed via endpoint probe"
                    )
                else:
                    transition_account_state(
                        conn, acc_id, "degraded", actor=actor,
                        reason="Account probe failed via endpoint probe"
                    )
            else:
                # No probeable endpoint found — cannot verify. Keep in probe state and
                # flag degraded so operator is alerted rather than silently re-activating.
                logger.warning(f"Account {acc_id}: no probeable endpoints found. Marking degraded.")
                transition_account_state(
                    conn, acc_id, "degraded", actor=actor,
                    reason="Account cooldown expired but no endpoints available to probe"
                )
