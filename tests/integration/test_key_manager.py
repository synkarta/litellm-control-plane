import pytest
import httpx
import tempfile
import os
from src.config.db import init_db, get_db
from src.registry.models import NodeCreate, ConsumerCreate, ModelCreate
from src.registry import store, key_manager

class MockResponse:
    def __init__(self, json_data, status_code):
        self._json_data = json_data
        self.status_code = status_code
        self.text = "Mock Error"

    def json(self):
        return self._json_data

class MockHTTPClient:
    def __init__(self):
        self.calls = []
        self.response = MockResponse({"key": "sk-mocked-virtual-key-123"}, 200)
        self.should_fail = False

    def post(self, url, json, headers):
        self.calls.append(("POST", url, json, headers))
        if self.should_fail:
            raise httpx.RequestError("Mocked Connection Failure")
        return self.response

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

def test_key_manager_integration(temp_db, monkeypatch):
    mock_client = MockHTTPClient()
    
    # Patch LiteLLMAdapter inside key_manager to use our mock HTTP client
    monkeypatch.setattr(
        "src.registry.key_manager.LiteLLMAdapter",
        lambda url, key: type("MockAdapter", (), {
            "generate_key": lambda self, models, metadata, max_budget=None, rate_limit_rpm=None, rate_limit_tpm=None: mock_client.post(
                f"{url}/key/generate",
                {"models": models, "metadata": metadata, "max_budget": max_budget, "rate_limit_rpm": rate_limit_rpm, "rate_limit_tpm": rate_limit_tpm},
                {"Authorization": f"Bearer {key}"}
            ).json(),
            "update_key": lambda self, key_val, models, metadata, max_budget=None, rate_limit_rpm=None, rate_limit_tpm=None: mock_client.post(
                f"{url}/key/update",
                {"key": key_val, "models": models, "metadata": metadata, "max_budget": max_budget, "rate_limit_rpm": rate_limit_rpm, "rate_limit_tpm": rate_limit_tpm},
                {"Authorization": f"Bearer {key}"}
            ).json(),
            "delete_key": lambda self, key_val: mock_client.post(
                f"{url}/key/delete",
                {"keys": [key_val]},
                {"Authorization": f"Bearer {key}"}
            ).status_code == 200
        })()
    )

    with get_db(temp_db) as conn:
        # Create active Proxy node and a model group
        store.create_node(conn, NodeCreate(id="node-1", name="N1", host="localhost", port=4000, region="us", role="proxy"), actor="admin")
        store.create_model(conn, ModelCreate(id="m1", name="gpt-4o", logical_group="premium"), actor="admin")
        
        # Create Consumer
        store.create_consumer(conn, ConsumerCreate(id="c1", name="Consumer 1", max_budget=100.0), actor="admin")
        
        # 1. Test standard Key Generation (Success)
        key_manager.sync_consumer_to_all_nodes(conn, "c1")
        
        # Verify Key exists in DB
        db_key = store.get_consumer_key(conn, "c1", "node-1")
        assert db_key is not None
        assert db_key.virtual_key == "sk-mocked-virtual-key-123"
        assert db_key.status == "active"
        assert len(mock_client.calls) == 1
        
        # 2. Test eventual consistency (Sync failure -> pending-sync status)
        mock_client.should_fail = True
        store.create_consumer(conn, ConsumerCreate(id="c2", name="Consumer 2"), actor="admin")
        
        key_manager.sync_consumer_to_all_nodes(conn, "c2")
        db_key_stale = store.get_consumer_key(conn, "c2", "node-1")
        assert db_key_stale is not None
        assert db_key_stale.status == "pending-sync"
        assert db_key_stale.virtual_key.startswith("pending-key-")
        
        # 3. Test key reconciliation (Restore connection success -> active status)
        mock_client.should_fail = False
        mock_client.response = MockResponse({"key": "sk-reconciled-key-999"}, 200)
        
        key_manager.reconcile_all_keys(conn)
        db_key_resolved = store.get_consumer_key(conn, "c2", "node-1")
        assert db_key_resolved is not None
        assert db_key_resolved.status == "active"
        assert db_key_resolved.virtual_key == "sk-reconciled-key-999"
        
        # 4. Test Key Revocation / Deletion
        key_manager.delete_consumer_from_all_nodes(conn, "c1")
        assert store.get_consumer_key(conn, "c1", "node-1") is None
        # Call history should contain delete_key call
        assert mock_client.calls[-1][1].endswith("/key/delete")
