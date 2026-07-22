import os
import tempfile
import pytest
from src.config.db import init_db, get_db
from src.registry import store
from src.registry.models import (
    NodeCreate, ProviderCreate, ModelCreate, AccountCreate, EndpointCreate,
    ConsumerCreate, PolicyProfileCreate
)
from src.policy import engine
from src.registry import key_manager

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

def test_policy_scoping_and_candidate_resolution(temp_db):
    with get_db(temp_db) as conn:
        # Create Policy Profiles
        store.create_policy_profile(
            conn,
            PolicyProfileCreate(
                id="coding-profile",
                name="Coding Profile",
                allowed_model_groups='["premium", "coding"]',
                description="Allowed models for developers"
            ),
            actor="admin"
        )
        
        # Create Consumers
        store.create_consumer(
            conn,
            ConsumerCreate(
                id="c-developer",
                name="Developer Consumer",
                profile_id="coding-profile"
            ),
            actor="admin"
        )
        store.create_consumer(
            conn,
            ConsumerCreate(
                id="c-unscoped",
                name="Unscoped Consumer",
                profile_id=None
            ),
                actor="admin"
        )

        # Create Nodes
        store.create_node(conn, NodeCreate(id="node-1", name="Node 1", host="localhost", port=4000, region="us", role="proxy"), actor="admin")
        
        # Create Providers
        store.create_provider(conn, ProviderCreate(id="openai", name="OpenAI", type="openai"), actor="admin")
        
        # Create Models
        store.create_model(conn, ModelCreate(id="m-gpt4", name="gpt-4", logical_group="premium"), actor="admin")
        store.create_model(conn, ModelCreate(id="m-llama", name="llama", logical_group="general"), actor="admin")
        store.create_model(conn, ModelCreate(id="m-codegen", name="codegen", logical_group="coding"), actor="admin")
        
        # Create Accounts
        store.create_account(conn, AccountCreate(id="acc-openai", name="OpenAI Personal", provider_id="openai", secret_ref="doppler://p/c/KEY"), actor="admin")
        
        # Create Endpoints
        store.create_endpoint(conn, EndpointCreate(id="ep-gpt4", node_id="node-1", account_id="acc-openai", model_id="m-gpt4", priority=1, weight=100), actor="admin")
        store.create_endpoint(conn, EndpointCreate(id="ep-llama", node_id="node-1", account_id="acc-openai", model_id="m-llama", priority=1, weight=100), actor="admin")
        store.create_endpoint(conn, EndpointCreate(id="ep-codegen", node_id="node-1", account_id="acc-openai", model_id="m-codegen", priority=1, weight=100), actor="admin")

    with get_db(temp_db) as conn:
        # Test key manager scoping
        scope_dev = key_manager.get_consumer_models_scope(conn, "c-developer")
        assert "premium" in scope_dev
        assert "coding" in scope_dev
        assert "general" not in scope_dev

        scope_unscoped = key_manager.get_consumer_models_scope(conn, "c-unscoped")
        assert len(scope_unscoped) == 0

        # Test Candidate Resolution in Policy Engine
        # allowed group -> should return endpoints
        candidates = engine.get_candidate_endpoints(conn, "c-developer", "premium")
        assert len(candidates) == 1
        assert candidates[0].id == "ep-gpt4"

        # disallowed group -> should return empty
        candidates_general = engine.get_candidate_endpoints(conn, "c-developer", "general")
        assert len(candidates_general) == 0

        # Test Health & Override Exclusions in Policy Engine
        # 1. Degrade ep-gpt4
        store.update_endpoint_status(conn, "ep-gpt4", status="degraded", manual_override="none", actor="admin")
        candidates = engine.get_candidate_endpoints(conn, "c-developer", "premium")
        assert len(candidates) == 0

        # 2. Force active override on degraded endpoint
        store.update_endpoint_status(conn, "ep-gpt4", status="degraded", manual_override="force-active", actor="admin")
        candidates = engine.get_candidate_endpoints(conn, "c-developer", "premium")
        assert len(candidates) == 1
        assert candidates[0].id == "ep-gpt4"

        # 3. Disable account -> even force-active is excluded
        store.update_account_status(conn, "acc-openai", status="disabled", actor="admin")
        candidates = engine.get_candidate_endpoints(conn, "c-developer", "premium")
        assert len(candidates) == 0
