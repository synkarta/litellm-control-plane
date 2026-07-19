import os
import pytest
import httpx
from src.secrets.doppler import DopplerResolver

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
        self.response = MockResponse({"GEMINI_API_KEY": "secret-gemini-val"}, 200)

    def get(self, url, headers):
        self.calls.append((url, headers))
        return self.response

def test_parse_uri():
    resolver = DopplerResolver()
    project, config, name = resolver.parse_uri("doppler://my-project/stg/MY_KEY")
    assert project == "my-project"
    assert config == "stg"
    assert name == "MY_KEY"

    with pytest.raises(ValueError):
        resolver.parse_uri("doppler://my-project/stg") # missing name
    with pytest.raises(ValueError):
        resolver.parse_uri("bad://my-project/stg/MY_KEY") # wrong prefix

def test_token_normalization(monkeypatch):
    resolver = DopplerResolver()
    
    # Set env var for project: "my-proj", config: "stg-env"
    # Normalizes to: DOPPLER_TOKEN_MY_PROJ_STG_ENV
    monkeypatch.setenv("DOPPLER_TOKEN_MY_PROJ_STG_ENV", "dp.pt.123")
    token = resolver._get_token("my-proj", "stg-env")
    assert token == "dp.pt.123"

    # Verify fallback to general DOPPLER_TOKEN
    monkeypatch.delenv("DOPPLER_TOKEN_MY_PROJ_STG_ENV", raising=False)
    monkeypatch.setenv("DOPPLER_TOKEN", "dp.pt.default")
    token = resolver._get_token("my-proj", "stg-env")
    assert token == "dp.pt.default"

def test_resolve_from_doppler():
    mock_client = MockHTTPClient()
    resolver = DopplerResolver(client=mock_client)
    
    # Set mock environment token so Doppler lookup is active
    os.environ["DOPPLER_TOKEN_MY_PROJECT_STG"] = "dp.pt.test-token"
    
    try:
        val = resolver.resolve("doppler://my-project/stg/GEMINI_API_KEY")
        assert val == "secret-gemini-val"
        assert len(mock_client.calls) == 1
        
        url, headers = mock_client.calls[0]
        assert url == "https://api.doppler.com/v3/configs/config/secrets/download"
        assert headers["Authorization"] == "Bearer dp.pt.test-token"
    finally:
        del os.environ["DOPPLER_TOKEN_MY_PROJECT_STG"]

def test_caching():
    mock_client = MockHTTPClient()
    resolver = DopplerResolver(cache_ttl=5.0, client=mock_client)
    
    os.environ["DOPPLER_TOKEN_P_C"] = "tok"
    try:
        # First resolve
        resolver.resolve("doppler://p/c/GEMINI_API_KEY")
        # Second resolve (should hit cache)
        resolver.resolve("doppler://p/c/GEMINI_API_KEY")
        
        assert len(mock_client.calls) == 1
    finally:
        del os.environ["DOPPLER_TOKEN_P_C"]

def test_fallback_to_local_env(monkeypatch):
    resolver = DopplerResolver()
    
    # No Doppler token is set for P_C
    monkeypatch.delenv("DOPPLER_TOKEN_P_C", raising=False)
    monkeypatch.delenv("DOPPLER_TOKEN", raising=False)
    
    # Set local env secret variable
    monkeypatch.setenv("GEMINI_API_KEY", "local-gemini-key")
    
    # Resolution should fallback to reading local env var because token is missing
    val = resolver.resolve("doppler://p/c/GEMINI_API_KEY")
    assert val == "local-gemini-key"

def test_fallback_on_doppler_error(monkeypatch):
    mock_client = MockHTTPClient()
    # Set response to a failing status code
    mock_client.response = MockResponse({}, 500)
    
    resolver = DopplerResolver(client=mock_client)
    
    monkeypatch.setenv("DOPPLER_TOKEN_P_C", "tok")
    monkeypatch.setenv("GEMINI_API_KEY", "local-fail-fallback")
    
    # Should call Doppler, fail, print warning, and fallback to local env
    val = resolver.resolve("doppler://p/c/GEMINI_API_KEY")
    assert val == "local-fail-fallback"
    assert len(mock_client.calls) == 1
