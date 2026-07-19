import pytest
from src.adapters.litellm_adapter import LiteLLMAdapter

class MockResponse:
    def __init__(self, json_data, status_code):
        self._json_data = json_data
        self.status_code = status_code
        self.text = "Mock Error text"

    def json(self):
        return self._json_data

class MockHTTPClient:
    def __init__(self):
        self.calls = []
        self.response = MockResponse({"key": "sk-mock-virtual-key"}, 200)

    def get(self, url):
        self.calls.append(("GET", url, None, None))
        return self.response

    def post(self, url, json, headers):
        self.calls.append(("POST", url, json, headers))
        return self.response

def test_check_health():
    mock_client = MockHTTPClient()
    adapter = LiteLLMAdapter("http://localhost:4000", "master-key", client=mock_client)
    
    mock_client.response = MockResponse({}, 200)
    assert adapter.check_health() is True
    assert mock_client.calls[0] == ("GET", "http://localhost:4000/health/readiness", None, None)

    # Failed health check
    mock_client.response = MockResponse({}, 500)
    assert adapter.check_health() is False

def test_generate_key():
    mock_client = MockHTTPClient()
    adapter = LiteLLMAdapter("http://localhost:4000", "master-key", client=mock_client)
    
    mock_client.response = MockResponse({"key": "sk-123", "max_budget": 50}, 200)
    res = adapter.generate_key(
        models=["premium"],
        metadata={"user": "developer"},
        max_budget=50.0,
        rate_limit_rpm=10
    )
    assert res["key"] == "sk-123"
    assert len(mock_client.calls) == 1
    
    method, url, json_body, headers = mock_client.calls[0]
    assert method == "POST"
    assert url == "http://localhost:4000/key/generate"
    assert headers["Authorization"] == "Bearer master-key"
    assert json_body["models"] == ["premium"]
    assert json_body["max_budget"] == 50.0
    assert json_body["rate_limit_rpm"] == 10

def test_update_key():
    mock_client = MockHTTPClient()
    adapter = LiteLLMAdapter("http://localhost:4000", "master-key", client=mock_client)
    
    mock_client.response = MockResponse({"key": "sk-123"}, 200)
    res = adapter.update_key(
        key="sk-123",
        models=["premium", "general"],
        metadata={"user": "operator"},
        max_budget=100.0
    )
    assert res["key"] == "sk-123"
    assert len(mock_client.calls) == 1
    
    method, url, json_body, headers = mock_client.calls[0]
    assert method == "POST"
    assert url == "http://localhost:4000/key/update"
    assert json_body["key"] == "sk-123"
    assert json_body["models"] == ["premium", "general"]
    assert json_body["max_budget"] == 100.0

def test_delete_key():
    mock_client = MockHTTPClient()
    adapter = LiteLLMAdapter("http://localhost:4000", "master-key", client=mock_client)
    
    mock_client.response = MockResponse({}, 200)
    assert adapter.delete_key("sk-123") is True
    
    method, url, json_body, headers = mock_client.calls[0]
    assert method == "POST"
    assert url == "http://localhost:4000/key/delete"
    assert json_body["keys"] == ["sk-123"]
