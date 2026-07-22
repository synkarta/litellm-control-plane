import os
import tempfile
import pytest
import sqlite3
import yaml
from fastapi.testclient import TestClient

from src.api.main import app
from src.config.db import get_db, init_db
from src.registry import store
from src.registry.models import (
    NodeCreate, ProviderCreate, ModelCreate,
    AccountCreate, EndpointCreate, ConsumerCreate,
    ConsumerKeyCreate
)
from src.rollout.orchestrator import RolloutOrchestrator
from src.config.generator import ConfigGenerator
from src.secrets.doppler import DopplerResolver

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    init_db(path)
    yield path
    try:
        os.remove(path)
    except Exception:
        pass

@pytest.fixture
def temp_config_file():
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except Exception:
        pass

class MockAdapter:
    def __init__(self, healthy=True):
        self.healthy = healthy
    def check_health(self):
        return self.healthy
    def generate_key(self, **kwargs):
        return {"key": "sk-reconciled-key"}
    def delete_key(self, key):
        return True

def test_metrics_endpoint():
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "litellm_requests_total" in response.text

def test_timeline_endpoint(temp_db):
    with get_db(temp_db) as conn:
        # Create an incident
        store.create_incident(conn, "endpoint", "ep-1", "active", "cooldown", "Transient 429", None)
        # Create an audit log
        store.log_audit(conn, "admin", "create", "node", "node-1", {"name": "Test Node"}, "Initial setup")
        
        # Test unified timeline retrieval
        timeline = store.get_unified_timeline(conn, limit=10)
        assert len(timeline) == 2
        
        incident = [t for t in timeline if t["event_type"] == "incident"][0]
        assert incident["actor"] == "system"
        assert incident["details"]["state_to"] == "cooldown"

        audit = [t for t in timeline if t["event_type"] == "audit"][0]
        assert audit["actor"] == "admin"
        assert audit["details"]["changes"]["name"] == "Test Node"

def test_auto_reconciliation(temp_db, temp_config_file, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key")
    
    with get_db(temp_db) as conn:
        store.create_node(conn, NodeCreate(id="node-test", name="Test Proxy", host="localhost", port=4000, region="us", role="proxy"), actor="admin")
        store.create_provider(conn, ProviderCreate(id="openai", name="OpenAI", type="openai"), actor="admin")
        store.create_model(conn, ModelCreate(id="m-gpt4", name="gpt-4", logical_group="premium"), actor="admin")
        store.create_account(conn, AccountCreate(id="acc-openai", name="OpenAI Personal", provider_id="openai", secret_ref="doppler://p/c/OPENAI_API_KEY"), actor="admin")
        store.create_endpoint(conn, EndpointCreate(id="ep-openai", node_id="node-test", account_id="acc-openai", model_id="m-gpt4", priority=1, weight=100), actor="admin")
        store.create_consumer(conn, ConsumerCreate(id="c-app", name="App Consumer"), actor="admin")
        store.create_consumer_key(conn, ConsumerKeyCreate(consumer_id="c-app", node_id="node-test", virtual_key="sk-test", status="active"), actor="admin")

    resolver = DopplerResolver()
    generator = ConfigGenerator(resolver)
    orchestrator = RolloutOrchestrator(generator)

    with get_db(temp_db) as conn:
        # Deploy config to align
        orchestrator.deploy_config(
            conn=conn,
            node_id="node-test",
            config_filepath=temp_config_file,
            timeout_sec=2.0,
            poll_interval_sec=0.1,
            mock_adapter=MockAdapter(healthy=True)
        )
        
        # Verify no initial drift
        res = orchestrator.reconcile_node(conn, "node-test", temp_config_file)
        assert res["reconciled"] is False

        # 1. Trigger Config Drift: modify file
        with open(temp_config_file, "w") as f:
            f.write("invalid_content: true")

        # Reconcile node -> should detect config drift and redeploy successfully
        res = orchestrator.reconcile_node(conn, "node-test", temp_config_file, timeout_sec=2.0, mock_adapter=MockAdapter(healthy=True))
        assert res["reconciled"] is True
        assert res["reconciled_config"] is True

        # Verify config rewritten correctly
        with open(temp_config_file, "r") as f:
            c = yaml.safe_load(f)
            assert c["model_list"][0]["model_name"] == "premium"

        # 2. Trigger Key Drift: add orphaned key
        store.create_consumer(conn, ConsumerCreate(id="c-orphan", name="Orphan Consumer", status="active"), actor="admin")
        store.create_consumer_key(conn, ConsumerKeyCreate(consumer_id="c-orphan", node_id="node-test", virtual_key="sk-orphan", status="active"), actor="admin")
        
        # Deactivate consumer to make the key on the node an orphan
        from src.registry.models import ConsumerUpdate
        store.update_consumer(conn, "c-orphan", ConsumerUpdate(status="disabled"), actor="admin")
        
        # Reconcile -> should detect key drift and delete the orphan key
        res = orchestrator.reconcile_node(conn, "node-test", temp_config_file, timeout_sec=2.0, mock_adapter=MockAdapter(healthy=True))
        assert res["reconciled"] is True
        assert res["reconciled_keys"] is True
        
        # Verify orphan key deleted
        key = store.get_consumer_key(conn, "c-orphan", "node-test")
        assert key is None
