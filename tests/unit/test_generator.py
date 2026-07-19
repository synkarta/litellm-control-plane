import os
import tempfile
import pytest
from src.config.db import init_db, get_db
from src.registry.models import (
    NodeCreate, ProviderCreate, ModelCreate, AccountCreate, EndpointCreate
)
from src.registry import store
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

def test_config_generation(temp_db, monkeypatch):
    # Setup test secrets in local env to bypass Doppler API calls via fallback
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-openai-key")
    monkeypatch.setenv("OLLAMA_API_KEY", "mock-ollama-key")
    monkeypatch.setenv("OLLAMA_API_BASE", "http://10.0.0.5:11434/api/")

    with get_db(temp_db) as conn:
        # Create Nodes
        store.create_node(conn, NodeCreate(id="node-test", name="Test Proxy", host="localhost", port=4000, region="us", role="proxy"), actor="admin")
        
        # Create Providers
        store.create_provider(conn, ProviderCreate(id="openai", name="OpenAI", type="openai"), actor="admin")
        store.create_provider(conn, ProviderCreate(id="ollama", name="Ollama Local", type="ollama"), actor="admin")
        
        # Create Models
        store.create_model(conn, ModelCreate(id="m-gpt4", name="gpt-4o", logical_group="premium"), actor="admin")
        store.create_model(conn, ModelCreate(id="m-llama", name="llama3.2", logical_group="general"), actor="admin")
        
        # Create Accounts
        store.create_account(conn, AccountCreate(id="acc-openai", name="OpenAI Personal", provider_id="openai", secret_ref="doppler://p/c/OPENAI_API_KEY"), actor="admin")
        store.create_account(conn, AccountCreate(id="acc-ollama", name="Ollama Personal", provider_id="ollama", secret_ref="doppler://p/c/OLLAMA_API_KEY"), actor="admin")
        
        # Create Endpoints
        store.create_endpoint(conn, EndpointCreate(id="ep-openai", node_id="node-test", account_id="acc-openai", model_id="m-gpt4", priority=1, weight=100), actor="admin")
        store.create_endpoint(conn, EndpointCreate(id="ep-ollama", node_id="node-test", account_id="acc-ollama", model_id="m-llama", priority=3, weight=80), actor="admin")

    # Initialize ConfigGenerator
    resolver = DopplerResolver()
    generator = ConfigGenerator(resolver)
    
    with get_db(temp_db) as conn:
        config = generator.generate_config(conn, "node-test")
        
        assert "model_list" in config
        model_list = config["model_list"]
        assert len(model_list) == 2
        
        # Validate OpenAI entry
        openai_entry = next(item for item in model_list if item["model_name"] == "premium")
        assert openai_entry["litellm_params"]["model"] == "gpt-4o"
        assert openai_entry["litellm_params"]["api_key"] == "sk-mock-openai-key"
        assert openai_entry["litellm_params"]["order"] == 1
        assert openai_entry["litellm_params"]["weight"] == 100
        assert "api_base" not in openai_entry["litellm_params"]
        
        # Validate Ollama entry (prefix added, api_base resolved and sanitized)
        ollama_entry = next(item for item in model_list if item["model_name"] == "general")
        assert ollama_entry["litellm_params"]["model"] == "ollama/llama3.2"
        assert ollama_entry["litellm_params"]["api_key"] == "mock-ollama-key"
        assert ollama_entry["litellm_params"]["order"] == 3
        assert ollama_entry["litellm_params"]["weight"] == 80
        # /api/ suffix should have been stripped
        assert ollama_entry["litellm_params"]["api_base"] == "http://10.0.0.5:11434"

        # Test dynamic exclusions (disable OpenAI endpoint)
        store.update_endpoint_status(conn, "ep-openai", status="disabled", manual_override="none", actor="admin")
        config_disabled = generator.generate_config(conn, "node-test")
        assert len(config_disabled["model_list"]) == 1
        assert config_disabled["model_list"][0]["model_name"] == "general"

        # Test manual override force-active on Ollama (lowers priority order value to 1)
        store.update_endpoint_status(conn, "ep-ollama", status="active", manual_override="force-active", actor="admin")
        config_override = generator.generate_config(conn, "node-test")
        assert config_override["model_list"][0]["litellm_params"]["order"] == 1
