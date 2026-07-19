import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.config.db import init_db

@pytest.fixture
def api_client():
    # Setup temporary database for integration tests
    fd, db_path = tempfile.mkstemp()
    os.close(fd)
    
    # Configure app to use the temp DB via env var
    os.environ["DATABASE_URL"] = db_path
    init_db(db_path)
    
    # Enable test client
    client = TestClient(app)
    yield client
    
    # Clean up
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]
    try:
        os.remove(db_path)
    except OSError:
        pass

def test_health_check_is_public(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_registry_requires_auth(api_client):
    # No header
    response = api_client.get("/registry/nodes")
    assert response.status_code == 401

    # Bad header
    response = api_client.get("/registry/nodes", headers={"X-Admin-API-Key": "wrong-key"})
    assert response.status_code == 401

def test_full_registry_crud_via_api(api_client):
    headers = {"X-Admin-API-Key": "admin-api-key-123"}

    # 1. Create Node
    node_payload = {
        "id": "node-kr-1",
        "name": "Korea Node",
        "host": "10.0.0.1",
        "port": 4000,
        "region": "ap-northeast-2",
        "role": "proxy",
        "status": "active"
    }
    response = api_client.post("/registry/nodes", json=node_payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == "node-kr-1"

    # 2. Create Provider
    provider_payload = {
        "id": "openai",
        "name": "OpenAI Inc",
        "type": "openai"
    }
    response = api_client.post("/registry/providers", json=provider_payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == "openai"

    # 3. Create Model
    model_payload = {
        "id": "gpt-4o",
        "name": "openai/gpt-4o",
        "logical_group": "premium-chat",
        "capability_chat": True,
        "capability_stream": True,
        "capability_tools": True,
        "capability_embeddings": False
    }
    response = api_client.post("/registry/models", json=model_payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == "gpt-4o"

    # 4. Create Account
    account_payload = {
        "id": "acc-openai",
        "name": "Production Account",
        "provider_id": "openai",
        "secret_ref": "doppler://PROJECT/CONFIG/KEY",
        "status": "active"
    }
    response = api_client.post("/registry/accounts", json=account_payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == "acc-openai"

    # 5. Create Endpoint
    endpoint_payload = {
        "id": "ep-kr-gpt4o",
        "node_id": "node-kr-1",
        "account_id": "acc-openai",
        "model_id": "gpt-4o",
        "priority": 1,
        "weight": 100,
        "status": "active",
        "manual_override": "none"
    }
    response = api_client.post("/registry/endpoints", json=endpoint_payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == "ep-kr-gpt4o"

    # 6. Verify Listings
    response = api_client.get("/registry/endpoints", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    # 7. Update Endpoint Routing
    response = api_client.post("/registry/endpoints/ep-kr-gpt4o/routing?priority=2&weight=80", headers=headers)
    assert response.status_code == 200
    assert response.json()["priority"] == 2
    assert response.json()["weight"] == 80

    # 8. Update Endpoint Status/Override
    response = api_client.post("/registry/endpoints/ep-kr-gpt4o/status?status=degraded&manual_override=force-disabled", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["manual_override"] == "force-disabled"

    # 9. Update Account Status
    response = api_client.post("/registry/accounts/acc-openai/status?status=cooldown", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cooldown"

    # 10. Check Audit Logs
    response = api_client.get("/audit-logs", headers=headers)
    assert response.status_code == 200
    logs = response.json()
    assert len(logs) > 0
    # Audit log should record the status updates and creation actions
    actions = [log["action"] for log in logs]
    assert "create" in actions
    assert "update_status" in actions

    # 11. Clean Up / Deletion
    assert api_client.delete("/registry/endpoints/ep-kr-gpt4o", headers=headers).status_code == 200
    assert api_client.delete("/registry/accounts/acc-openai", headers=headers).status_code == 200
    assert api_client.delete("/registry/models/gpt-4o", headers=headers).status_code == 200
    assert api_client.delete("/registry/providers/openai", headers=headers).status_code == 200
    assert api_client.delete("/registry/nodes/node-kr-1", headers=headers).status_code == 200

def test_consumer_api_flow(api_client):
    headers = {"X-Admin-API-Key": "admin-api-key-123", "X-Actor": "test-actor"}

    # 1. Create Consumer
    consumer_data = {
        "id": "c-integration",
        "name": "Integration Customer",
        "max_budget": 50.0,
        "rate_limit_rpm": 10,
        "rate_limit_tpm": 50000,
        "status": "active"
    }
    response = api_client.post("/registry/consumers", json=consumer_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == "c-integration"

    # 2. Get Consumer
    response = api_client.get("/registry/consumers/c-integration", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Integration Customer"

    # 3. List Consumers
    response = api_client.get("/registry/consumers", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    # 4. Patch Consumer
    patch_data = {"name": "Integration Customer Extended", "max_budget": 75.0}
    response = api_client.patch("/registry/consumers/c-integration", json=patch_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Integration Customer Extended"
    assert response.json()["max_budget"] == 75.0

    # 5. List Consumer Keys (should be empty initially)
    response = api_client.get("/registry/consumers/c-integration/keys", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 0

    # 6. Delete Consumer
    response = api_client.delete("/registry/consumers/c-integration", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"detail": "Consumer deleted"}

    # Get should 404 now
    assert api_client.get("/registry/consumers/c-integration", headers=headers).status_code == 404

