import os
import tempfile
import pytest
import yaml
from src.config.db import init_db, get_db
from src.registry import store
from src.registry.models import (
    NodeCreate, ProviderCreate, ModelCreate, AccountCreate, EndpointCreate,
    ConsumerCreate
)
from src.secrets.doppler import DopplerResolver
from src.config.generator import ConfigGenerator
from src.rollout.orchestrator import RolloutOrchestrator

class MockAdapter:
    def __init__(self, healthy: bool):
        self.healthy = healthy

    def check_health(self) -> bool:
        return self.healthy

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
def temp_config_file():
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass

def test_rollout_orchestration_flow(temp_db, temp_config_file, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key")

    with get_db(temp_db) as conn:
        store.create_node(conn, NodeCreate(id="node-test", name="Test Proxy", host="localhost", port=4000, region="us", role="proxy"), actor="admin")
        store.create_provider(conn, ProviderCreate(id="openai", name="OpenAI", type="openai"), actor="admin")
        store.create_model(conn, ModelCreate(id="m-gpt4", name="gpt-4", logical_group="premium"), actor="admin")
        store.create_account(conn, AccountCreate(id="acc-openai", name="OpenAI Personal", provider_id="openai", secret_ref="doppler://p/c/OPENAI_API_KEY"), actor="admin")
        store.create_endpoint(conn, EndpointCreate(id="ep-openai", node_id="node-test", account_id="acc-openai", model_id="m-gpt4", priority=1, weight=100), actor="admin")
        store.create_consumer(conn, ConsumerCreate(id="c-app", name="App Consumer"), actor="admin")
        from src.registry.models import ConsumerKeyCreate
        store.create_consumer_key(conn, ConsumerKeyCreate(consumer_id="c-app", node_id="node-test", virtual_key="sk-test", status="active"), actor="admin")

    resolver = DopplerResolver()
    generator = ConfigGenerator(resolver)
    orchestrator = RolloutOrchestrator(generator)

    # 1. Test Successful Rollout
    with get_db(temp_db) as conn:
        res = orchestrator.deploy_config(
            conn=conn,
            node_id="node-test",
            config_filepath=temp_config_file,
            timeout_sec=2.0,
            poll_interval_sec=0.1,
            mock_adapter=MockAdapter(healthy=True)
        )
        assert res["status"] == "success"
        
        # Verify file written
        with open(temp_config_file, "r", encoding="utf-8") as f:
            disk_config = yaml.safe_load(f)
            assert disk_config["model_list"][0]["model_name"] == "premium"

        # Verify DB rollout status
        rollout = store.get_rollout(conn, res["rollout_id"])
        assert rollout.status == "success"

    # 2. Test Failed Rollout with Automatic Rollback
    # First, let's create a drift by disabling the endpoint so desired state changes
    with get_db(temp_db) as conn:
        store.update_endpoint_status(conn, "ep-openai", status="disabled", manual_override="none", actor="admin")
        
        # Deploy config with a failing health probe -> should rollback to previous success
        with pytest.raises(RuntimeError, match="Rollout verification failed"):
            orchestrator.deploy_config(
                conn=conn,
                node_id="node-test",
                config_filepath=temp_config_file,
                timeout_sec=1.0,
                poll_interval_sec=0.1,
                mock_adapter=MockAdapter(healthy=False)
            )

        # Config file should have been rolled back to the previous success (which has model premium)
        with open(temp_config_file, "r", encoding="utf-8") as f:
            rolled_back_config = yaml.safe_load(f)
            assert len(rolled_back_config["model_list"]) == 1
            assert rolled_back_config["model_list"][0]["model_name"] == "premium"

        # Rollouts list should contain a 'rolled_back' rollout
        rollouts = store.list_rollouts(conn, node_id="node-test")
        assert any(r.status == "rolled_back" for r in rollouts)

def test_drift_detection(temp_db, temp_config_file, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key")

    with get_db(temp_db) as conn:
        store.create_node(conn, NodeCreate(id="node-test", name="Test Proxy", host="localhost", port=4000, region="us", role="proxy"), actor="admin")
        store.create_provider(conn, ProviderCreate(id="openai", name="OpenAI", type="openai"), actor="admin")
        store.create_model(conn, ModelCreate(id="m-gpt4", name="gpt-4", logical_group="premium"), actor="admin")
        store.create_account(conn, AccountCreate(id="acc-openai", name="OpenAI Personal", provider_id="openai", secret_ref="doppler://p/c/OPENAI_API_KEY"), actor="admin")
        store.create_endpoint(conn, EndpointCreate(id="ep-openai", node_id="node-test", account_id="acc-openai", model_id="m-gpt4", priority=1, weight=100), actor="admin")
        store.create_consumer(conn, ConsumerCreate(id="c-app", name="App Consumer"), actor="admin")
        from src.registry.models import ConsumerKeyCreate
        store.create_consumer_key(conn, ConsumerKeyCreate(consumer_id="c-app", node_id="node-test", virtual_key="sk-test", status="active"), actor="admin")

    resolver = DopplerResolver()
    generator = ConfigGenerator(resolver)
    orchestrator = RolloutOrchestrator(generator)

    with get_db(temp_db) as conn:
        # Deploy first to align states
        orchestrator.deploy_config(
            conn=conn,
            node_id="node-test",
            config_filepath=temp_config_file,
            timeout_sec=2.0,
            poll_interval_sec=0.1,
            mock_adapter=MockAdapter(healthy=True)
        )

        # Detect drift - should be False initially
        drift = orchestrator.detect_drift(conn, "node-test", temp_config_file)
        assert drift["drift_detected"] is False

        # Create config drift: manually modify config file
        with open(temp_config_file, "w", encoding="utf-8") as f:
            f.write("model_list: []")

        drift = orchestrator.detect_drift(conn, "node-test", temp_config_file)
        assert drift["config_drift"] is True
        assert drift["drift_detected"] is True
        
        # Test key drift (missing key on node)
        # Create another active consumer, but no consumer key on this node yet
        store.create_consumer(conn, ConsumerCreate(id="c-missing", name="Missing Key Consumer"), actor="admin")
        drift = orchestrator.detect_drift(conn, "node-test", temp_config_file)
        assert drift["key_drift"] is True
        assert "c-missing" in drift["missing_keys"]
