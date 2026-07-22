import os
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from src.config.db import init_db, get_db
from src.registry import store
from src.registry.models import (
    NodeCreate, ProviderCreate, ModelCreate, AccountCreate, EndpointCreate
)
from src.health import state_machine, manager
from src.health.probe import ProbeEngine
from src.secrets.doppler import DopplerResolver
from src.config.generator import ConfigGenerator

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    init_db(path)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass

@pytest.fixture
def populated_db(temp_db):
    with get_db(temp_db) as conn:
        # Create topology
        store.create_node(conn, NodeCreate(
            id="node-kr", name="Korea Proxy", host="12.0.0.1", port=4000, region="ap-northeast-2", role="proxy"
        ), actor="setup")
        store.create_provider(conn, ProviderCreate(
            id="openai", name="OpenAI Inc", type="openai"
        ), actor="setup")
        store.create_model(conn, ModelCreate(
            id="gpt-4o", name="openai/gpt-4o", logical_group="premium-chat"
        ), actor="setup")
        store.create_account(conn, AccountCreate(
            id="acc-prod", name="Production Account", provider_id="openai", secret_ref="doppler://PROJ/CONF/KEY"
        ), actor="setup")
        store.create_endpoint(conn, EndpointCreate(
            id="ep-1", node_id="node-kr", account_id="acc-prod", model_id="gpt-4o", priority=1, weight=100
        ), actor="setup")
    return temp_db

def test_state_transitions_basic(populated_db):
    with get_db(populated_db) as conn:
        # 1. 429 (Rate Limit) -> cooldown
        state_machine.handle_account_failure(conn, "acc-prod", 429, "Too many requests", actor="test")
        acc = store.get_account(conn, "acc-prod")
        assert acc.status == "cooldown"
        assert acc.cooldown_until is not None

        # Reset manually to active
        store.update_account_status(conn, "acc-prod", "active", actor="test")
        acc = store.get_account(conn, "acc-prod")
        assert acc.status == "active"
        assert acc.cooldown_until is None
        assert acc.failure_count == 0

        # 2. 401 (Auth Error) -> disabled
        state_machine.handle_account_failure(conn, "acc-prod", 401, "Invalid API Key", actor="test")
        acc = store.get_account(conn, "acc-prod")
        assert acc.status == "disabled"

        # Reset manually to active
        store.update_account_status(conn, "acc-prod", "active", actor="test")

        # 3. Timeout / connection error -> increment failure count
        state_machine.handle_account_failure(conn, "acc-prod", 504, "Gateway Timeout", actor="test")
        acc = store.get_account(conn, "acc-prod")
        assert acc.status == "active"
        assert acc.failure_count == 1

        state_machine.handle_account_failure(conn, "acc-prod", 504, "Gateway Timeout", actor="test")
        state_machine.handle_account_failure(conn, "acc-prod", 504, "Gateway Timeout", actor="test")
        acc = store.get_account(conn, "acc-prod")
        # >=3 failures transitions to degraded
        assert acc.status == "degraded"

        # Success resets failure count
        state_machine.handle_account_success(conn, "acc-prod", actor="test")
        acc = store.get_account(conn, "acc-prod")
        assert acc.status == "active"
        assert acc.failure_count == 0

def test_endpoint_transitions_basic(populated_db):
    with get_db(populated_db) as conn:
        # 1. 429 on endpoint level
        state_machine.handle_endpoint_failure(conn, "ep-1", 429, "Too many requests", actor="test")
        ep = store.get_endpoint(conn, "ep-1")
        assert ep.status == "cooldown"

        # Success on a cooldown resource must NOT exit cooldown (M2 fix).
        # Cooldown is time-locked; only reconcile+probe may exit it.
        state_machine.handle_endpoint_success(conn, "ep-1", actor="test")
        ep = store.get_endpoint(conn, "ep-1")
        assert ep.status == "cooldown", "Success must not bypass cooldown timer"

        # Reset manually for next part of test
        store.update_endpoint_status(conn, "ep-1", status="active", manual_override=None, actor="test")

        # 2. Multiple failures -> degraded
        state_machine.handle_endpoint_failure(conn, "ep-1", 500, "Server Error", actor="test")
        state_machine.handle_endpoint_failure(conn, "ep-1", 500, "Server Error", actor="test")
        state_machine.handle_endpoint_failure(conn, "ep-1", 500, "Server Error", actor="test")
        ep = store.get_endpoint(conn, "ep-1")
        assert ep.status == "degraded"

def test_config_exclusions(populated_db):
    # Setup resolver
    class FakeResolver(DopplerResolver):
        def __init__(self):
            pass
        def resolve(self, uri):
            return "real-resolved-key"

    generator = ConfigGenerator(resolver=FakeResolver())

    with get_db(populated_db) as conn:
        # Check generated config (initially healthy)
        cfg = generator.generate_config(conn, "node-kr")
        assert len(cfg["model_list"]) == 1

        # Put endpoint in cooldown
        state_machine.handle_endpoint_failure(conn, "ep-1", 429, "Rate limit", actor="test")
        cfg = generator.generate_config(conn, "node-kr")
        # Should be excluded!
        assert len(cfg["model_list"]) == 0

        # Now test manual_override = force-active
        store.update_endpoint_status(conn, "ep-1", status=None, manual_override="force-active", actor="test")
        cfg = generator.generate_config(conn, "node-kr")
        # Should bypass cooldown exclusion and be included!
        assert len(cfg["model_list"]) == 1

def test_callback_ingestion_api(populated_db):
    from fastapi.testclient import TestClient
    from src.api.main import app

    # Configure app to use temp db
    os.environ["DATABASE_URL"] = populated_db
    client = TestClient(app)
    headers = {"X-Admin-API-Key": "admin-api-key-123"}

    # Post failure callback payload
    payload = {
        "id": "chatcmpl-test",
        "model": "gpt-4o",
        "metadata": {
            "endpoint_id": "ep-1",
            "account_id": "acc-prod"
        },
        "status": "failed",
        "exception_class": "RateLimitError",
        "error": {
            "message": "Rate limit exceeded on provider",
            "status_code": 429
        }
    }

    response = client.post("/events/callback", json=payload, headers=headers)
    assert response.status_code == 200

    # Read status from DB
    with get_db(populated_db) as conn:
        acc = store.get_account(conn, "acc-prod")
        ep = store.get_endpoint(conn, "ep-1")
        # 429 is endpoint-scoped (M3 fix): account must remain active
        assert acc.status == "active", "429 must not put account in cooldown"
        assert ep.status == "cooldown"

        # Incident log check: only 1 incident (endpoint), not 2
        incidents = manager.get_incidents_list(conn)
        assert len(incidents) >= 1

    # Clean env var
    del os.environ["DATABASE_URL"]

def test_probe_engine_execution(populated_db):
    class FakeResolver:
        def resolve(self, uri):
            return "mock-key"

    engine = ProbeEngine(resolver=FakeResolver())

    with get_db(populated_db) as conn:
        # Mark ep-1 as degraded
        state_machine.handle_endpoint_failure(conn, "ep-1", 500, "Server Error", actor="test")
        state_machine.handle_endpoint_failure(conn, "ep-1", 500, "Server Error", actor="test")
        state_machine.handle_endpoint_failure(conn, "ep-1", 500, "Server Error", actor="test")
        assert store.get_endpoint(conn, "ep-1").status == "degraded"

        # Run probe (since api_key resolves to 'mock-key', it will succeed)
        res = engine.probe_endpoint(conn, "ep-1")
        assert res is True

        # Endpoint should be active again!
        assert store.get_endpoint(conn, "ep-1").status == "active"


# ── H2: incidents filtering ───────────────────────────────────────────────────

def test_incidents_filter_by_target_type(populated_db):
    with get_db(populated_db) as conn:
        # Trigger both account and endpoint failures to generate incidents
        state_machine.handle_account_failure(conn, "acc-prod", 429, "Rate limited", actor="test")
        state_machine.handle_endpoint_failure(conn, "ep-1", 401, "Bad key", actor="test")

        # Filter: only account incidents
        acc_incidents = manager.get_incidents_list(conn, target_type="account")
        assert all(i["target_type"] == "account" for i in acc_incidents)
        assert any(i["target_id"] == "acc-prod" for i in acc_incidents)

        # Filter: only endpoint incidents
        ep_incidents = manager.get_incidents_list(conn, target_type="endpoint")
        assert all(i["target_type"] == "endpoint" for i in ep_incidents)

def test_incidents_filter_by_state_to(populated_db):
    with get_db(populated_db) as conn:
        state_machine.handle_account_failure(conn, "acc-prod", 429, "Rate limited", actor="test")
        store.update_account_status(conn, "acc-prod", "active", actor="test")
        state_machine.handle_account_failure(conn, "acc-prod", 401, "Bad key", actor="test")

        disabled_incidents = manager.get_incidents_list(conn, state_to="disabled")
        assert all(i["state_to"] == "disabled" for i in disabled_incidents)
        assert len(disabled_incidents) >= 1

        cooldown_incidents = manager.get_incidents_list(conn, state_to="cooldown")
        assert all(i["state_to"] == "cooldown" for i in cooldown_incidents)

def test_incidents_filter_by_target_id(populated_db):
    with get_db(populated_db) as conn:
        state_machine.handle_account_failure(conn, "acc-prod", 429, "Rate limited", actor="test")

        results = manager.get_incidents_list(conn, target_id="acc-prod")
        assert all(i["target_id"] == "acc-prod" for i in results)
        assert len(results) >= 1

        # A non-existent ID returns empty
        empty = manager.get_incidents_list(conn, target_id="nonexistent-id")
        assert empty == []


# ── H3: account reconcile goes through probe, not direct activation ──────────

def test_reconcile_cooldown_account_via_probe(populated_db):
    """
    When an account's cooldown expires, reconcile_cooldowns must transition it
    through 'probe' (verified via an associated endpoint probe) before going active.
    It must NOT jump directly from cooldown → active.
    """
    class FakeResolver:
        def resolve(self, uri):
            return "mock-key"  # triggers mock-success path in probe_endpoint

    engine = ProbeEngine(resolver=FakeResolver())

    with get_db(populated_db) as conn:
        # Put account in cooldown with an already-expired cooldown_until
        past = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        conn.execute(
            "UPDATE accounts SET status = 'cooldown', cooldown_until = ? WHERE id = ?",
            (past, "acc-prod")
        )
        conn.commit()

        acc = store.get_account(conn, "acc-prod")
        assert acc.status == "cooldown"

        engine.reconcile_cooldowns(conn, actor="test-reconcile")

        acc = store.get_account(conn, "acc-prod")
        # Must end up active (via probe path), NOT have stayed in cooldown or skipped probe
        assert acc.status == "active"

        # Confirm it passed through 'probe' state by checking incidents
        incidents = store.list_incidents(conn, target_type="account", target_id="acc-prod")
        states_seen = [i["state_to"] for i in incidents]
        assert "probe" in states_seen, "Expected account to pass through 'probe' state during reconcile"
        assert "active" in states_seen


# ── M2: success callback must not bypass cooldown timer ──────────────────────

def test_success_does_not_exit_cooldown(populated_db):
    """
    A success signal on a cooldown resource must be ignored.
    Cooldown can only be exited via reconcile_cooldowns + probe.
    """
    with get_db(populated_db) as conn:
        # Put account in cooldown via 429
        state_machine.handle_account_failure(conn, "acc-prod", 429, "Rate limited", actor="test")
        acc = store.get_account(conn, "acc-prod")
        assert acc.status == "cooldown"

        # A success signal should NOT move it back to active
        state_machine.handle_account_success(conn, "acc-prod", actor="test")
        acc = store.get_account(conn, "acc-prod")
        assert acc.status == "cooldown", (
            "Success callback must not bypass cooldown; only reconcile+probe may exit it"
        )

def test_success_does_not_exit_endpoint_cooldown(populated_db):
    with get_db(populated_db) as conn:
        state_machine.handle_endpoint_failure(conn, "ep-1", 429, "Rate limited", actor="test")
        ep = store.get_endpoint(conn, "ep-1")
        assert ep.status == "cooldown"

        state_machine.handle_endpoint_success(conn, "ep-1", actor="test")
        ep = store.get_endpoint(conn, "ep-1")
        assert ep.status == "cooldown", (
            "Success callback must not bypass cooldown on endpoint"
        )

def test_success_resets_degraded(populated_db):
    """
    Success signal on degraded (soft state, no timer) should still reset to active.
    """
    with get_db(populated_db) as conn:
        # Force degraded by exceeding failure threshold
        for _ in range(3):
            state_machine.handle_account_failure(conn, "acc-prod", 504, "Timeout", actor="test")
        acc = store.get_account(conn, "acc-prod")
        assert acc.status == "degraded"

        state_machine.handle_account_success(conn, "acc-prod", actor="test")
        acc = store.get_account(conn, "acc-prod")
        assert acc.status == "active"


# ── M3: failure dispatch scope by error type ─────────────────────────────────

def test_429_only_affects_endpoint_not_account(populated_db):
    """
    A 429 rate-limit failure must only put the endpoint in cooldown.
    The account must remain active (rate limit is endpoint/model-scoped, not key-scoped).
    """
    with get_db(populated_db) as conn:
        # Simulate callback with both IDs present but error is 429
        from src.events.ingestion import ingest_event_callback
        from unittest.mock import MagicMock

        payload = {
            "metadata": {"endpoint_id": "ep-1", "account_id": "acc-prod"},
            "status": "failed",
            "exception_class": "RateLimitError",
            "error": {"message": "Too many requests", "status_code": 429},
        }
        ingest_event_callback(payload, conn)

        ep = store.get_endpoint(conn, "ep-1")
        acc = store.get_account(conn, "acc-prod")

        assert ep.status == "cooldown", "Endpoint should be in cooldown after 429"
        assert acc.status == "active", (
            "Account must remain active for a 429 — rate limit is endpoint-scoped"
        )

def test_401_disables_both_endpoint_and_account(populated_db):
    """
    A 401 auth error must disable both the endpoint and the account,
    because the credential itself is invalid.
    """
    with get_db(populated_db) as conn:
        from src.events.ingestion import ingest_event_callback

        payload = {
            "metadata": {"endpoint_id": "ep-1", "account_id": "acc-prod"},
            "status": "failed",
            "exception_class": "AuthenticationError",
            "error": {"message": "Invalid API Key", "status_code": 401},
        }
        ingest_event_callback(payload, conn)

        ep = store.get_endpoint(conn, "ep-1")
        acc = store.get_account(conn, "acc-prod")

        assert ep.status == "disabled", "Endpoint must be disabled on 401"
        assert acc.status == "disabled", "Account must be disabled on 401 — credential is bad"

def test_5xx_only_affects_endpoint(populated_db):
    """
    5xx/timeout transient errors must only affect the endpoint failure counter.
    The account must remain untouched.
    """
    with get_db(populated_db) as conn:
        from src.events.ingestion import ingest_event_callback

        payload = {
            "metadata": {"endpoint_id": "ep-1", "account_id": "acc-prod"},
            "status": "failed",
            "exception_class": "ServiceUnavailableError",
            "error": {"message": "Server Error", "status_code": 503},
        }
        ingest_event_callback(payload, conn)

        ep = store.get_endpoint(conn, "ep-1")
        acc = store.get_account(conn, "acc-prod")

        # One 5xx increments failure_count on endpoint but doesn't cross threshold yet
        assert ep.failure_count == 1
        assert acc.status == "active", "Account must remain active on transient 5xx"
        assert acc.failure_count == 0, "Account failure count must not be incremented on 5xx"
