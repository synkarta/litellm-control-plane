import os
import tempfile
import pytest
from pydantic import ValidationError
from src.config.db import init_db, get_db
from src.registry.models import (
    NodeCreate, ProviderCreate, ModelCreate, AccountCreate, EndpointCreate
)
from src.registry import store

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

def test_node_crud(temp_db):
    with get_db(temp_db) as conn:
        # Create
        node_in = NodeCreate(
            id="node-kr-1",
            name="Korea Node 1",
            host="10.0.0.5",
            port=4000,
            region="ap-northeast-2",
            role="proxy",
            status="active"
        )
        created = store.create_node(conn, node_in, actor="test-runner", reason="setup test node")
        assert created.id == "node-kr-1"
        assert created.status == "active"

        # Get
        retrieved = store.get_node(conn, "node-kr-1")
        assert retrieved is not None
        assert retrieved.name == "Korea Node 1"

        # List
        nodes = store.list_nodes(conn)
        assert len(nodes) == 1
        assert nodes[0].id == "node-kr-1"

        # Delete
        assert store.delete_node(conn, "node-kr-1", actor="test-runner")
        assert store.get_node(conn, "node-kr-1") is None
        assert len(store.list_nodes(conn)) == 0

def test_provider_crud(temp_db):
    with get_db(temp_db) as conn:
        provider_in = ProviderCreate(id="openai", name="OpenAI Inc", type="openai")
        created = store.create_provider(conn, provider_in, actor="admin")
        assert created.id == "openai"

        providers = store.list_providers(conn)
        assert len(providers) == 1
        assert providers[0].name == "OpenAI Inc"

        assert store.delete_provider(conn, "openai", actor="admin")
        assert store.get_provider(conn, "openai") is None

def test_model_crud(temp_db):
    with get_db(temp_db) as conn:
        model_in = ModelCreate(
            id="gemini-flash",
            name="gemini/gemini-2.5-flash",
            logical_group="general-chat",
            capability_chat=True,
            capability_stream=True,
            capability_tools=True,
            capability_embeddings=False
        )
        created = store.create_model(conn, model_in, actor="admin")
        assert created.id == "gemini-flash"
        assert created.capability_chat is True
        assert created.capability_embeddings is False

        retrieved = store.get_model(conn, "gemini-flash")
        assert retrieved.capability_chat is True
        assert retrieved.capability_embeddings is False

        models = store.list_models(conn)
        assert len(models) == 1
        assert models[0].id == "gemini-flash"

        assert store.delete_model(conn, "gemini-flash", actor="admin")
        assert store.get_model(conn, "gemini-flash") is None

def test_account_crud_and_doppler_validation(temp_db):
    # Test Doppler format validation in Pydantic
    with pytest.raises(ValidationError):
        AccountCreate(
            id="acc-1",
            name="Bad Ref Account",
            provider_id="openai",
            secret_ref="bad_ref_without_doppler_prefix",
            status="active"
        )

    with get_db(temp_db) as conn:
        # Create provider first
        store.create_provider(conn, ProviderCreate(id="openai", name="OpenAI", type="openai"), actor="admin")

        # Create account
        acc_in = AccountCreate(
            id="acc-1",
            name="OpenAI Account 1",
            provider_id="openai",
            secret_ref="doppler://PROJ/CONF/OPENAI_API_KEY",
            status="active"
        )
        created = store.create_account(conn, acc_in, actor="admin")
        assert created.id == "acc-1"
        assert created.secret_ref == "doppler://PROJ/CONF/OPENAI_API_KEY"

        # Update status
        updated = store.update_account_status(conn, "acc-1", "cooldown", actor="system", reason="429 cooldown trigger")
        assert updated.status == "cooldown"

        # Get
        retrieved = store.get_account(conn, "acc-1")
        assert retrieved.status == "cooldown"

        # Attempt to create with invalid provider (should raise ValueError due to FK)
        acc_bad = AccountCreate(
            id="acc-bad",
            name="Bad Account",
            provider_id="nonexistent-provider",
            secret_ref="doppler://PROJ/CONF/KEY",
            status="active"
        )
        with pytest.raises(ValueError):
            store.create_account(conn, acc_bad, actor="admin")

def test_endpoint_crud_with_routing_and_overrides(temp_db):
    with get_db(temp_db) as conn:
        # Setup foreign keys
        store.create_node(conn, NodeCreate(id="node-1", name="Node 1", host="10.0.0.1", port=4000, region="us", role="proxy"), actor="admin")
        store.create_provider(conn, ProviderCreate(id="openai", name="OpenAI", type="openai"), actor="admin")
        store.create_account(conn, AccountCreate(id="acc-1", name="Acc 1", provider_id="openai", secret_ref="doppler://P/C/S"), actor="admin")
        store.create_model(conn, ModelCreate(id="model-1", name="gpt-4o", logical_group="premium-chat"), actor="admin")

        # Create endpoint
        ep_in = EndpointCreate(
            id="ep-1",
            node_id="node-1",
            account_id="acc-1",
            model_id="model-1",
            priority=1,
            weight=80,
            status="active",
            manual_override="none"
        )
        created = store.create_endpoint(conn, ep_in, actor="admin")
        assert created.id == "ep-1"
        assert created.priority == 1
        assert created.weight == 80
        assert created.manual_override == "none"

        # Update routing (priority/weight)
        updated_routing = store.update_endpoint_routing(conn, "ep-1", priority=2, weight=50, actor="admin")
        assert updated_routing.priority == 2
        assert updated_routing.weight == 50

        # Update status & override
        updated_status = store.update_endpoint_status(conn, "ep-1", status="degraded", manual_override="force-disabled", actor="operator")
        assert updated_status.status == "degraded"
        assert updated_status.manual_override == "force-disabled"

        # List endpoints
        endpoints = store.list_endpoints(conn)
        assert len(endpoints) == 1
        assert endpoints[0].id == "ep-1"

        # Try inserting bad endpoint (invalid keys)
        ep_bad = EndpointCreate(id="ep-bad", node_id="nonexistent", account_id="acc-1", model_id="model-1")
        with pytest.raises(ValueError):
            store.create_endpoint(conn, ep_bad, actor="admin")

def test_audit_logs(temp_db):
    with get_db(temp_db) as conn:
        # Perform some database operations
        store.create_node(conn, NodeCreate(id="node-test", name="Test Node", host="1.1.1.1", port=80, region="us", role="proxy"), actor="user-john", reason="onboarding")
        
        # Query audit logs
        logs = store.list_audit_logs(conn)
        assert len(logs) == 1
        log = logs[0]
        assert log["actor"] == "user-john"
        assert log["action"] == "create"
        assert log["target_type"] == "node"
        assert log["target_id"] == "node-test"
        assert log["reason"] == "onboarding"
        assert log["changes"]["id"] == "node-test"
        assert log["changes"]["name"] == "Test Node"

def test_node_update(temp_db):
    with get_db(temp_db) as conn:
        store.create_node(conn, NodeCreate(id="n1", name="Old Name", host="10.0.0.1", port=4000, region="us", role="proxy"), actor="admin")

        from src.registry.models import NodeUpdate
        # Partial update: only name and status
        updated = store.update_node(conn, "n1", NodeUpdate(name="New Name", status="degraded"), actor="health-manager", reason="health degraded")
        assert updated.name == "New Name"
        assert updated.status == "degraded"
        # Unupdated fields should be unchanged
        assert updated.host == "10.0.0.1"
        assert updated.port == 4000

        # Audit log should have been written
        logs = store.list_audit_logs(conn)
        update_log = next(l for l in logs if l["action"] == "update" and l["target_type"] == "node")
        assert update_log["actor"] == "health-manager"
        assert update_log["changes"]["after"]["status"] == "degraded"

def test_provider_update(temp_db):
    with get_db(temp_db) as conn:
        store.create_provider(conn, ProviderCreate(id="prov-1", name="Old Name", type="openai"), actor="admin")

        from src.registry.models import ProviderUpdate
        updated = store.update_provider(conn, "prov-1", ProviderUpdate(name="New Name"), actor="admin")
        assert updated.name == "New Name"
        assert updated.type == "openai"  # unchanged

def test_model_update(temp_db):
    with get_db(temp_db) as conn:
        store.create_model(conn, ModelCreate(id="m1", name="old-model", logical_group="chat", capability_embeddings=False), actor="admin")

        from src.registry.models import ModelUpdate
        # Enable embeddings capability
        updated = store.update_model(conn, "m1", ModelUpdate(name="new-model", capability_embeddings=True), actor="admin")
        assert updated.name == "new-model"
        assert updated.capability_embeddings is True
        assert updated.capability_chat is True  # unchanged

        # Verify it round-trips correctly through get_model
        retrieved = store.get_model(conn, "m1")
        assert retrieved.capability_embeddings is True
