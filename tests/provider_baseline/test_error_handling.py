import httpx
import pytest
from tests.provider_baseline.test_chat import should_skip

def test_auth_error_gemini(litellm_proxy_url):
    # Call invalid-gemini model which is configured with a bad API key
    url = f"{litellm_proxy_url}/v1/chat/completions"
    payload = {
        "model": "invalid-gemini",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    
    response = httpx.post(url, json=payload, timeout=20.0)
    # LiteLLM should translate upstream authentication/key errors to 401 Unauthorized or 400/403
    assert response.status_code in [400, 401, 403], f"Expected auth error, got: {response.status_code} - {response.text}"
    print(f"\ninvalid-gemini successfully returned auth error: {response.status_code}")

def test_auth_error_nim(litellm_proxy_url):
    # Call invalid-nim model which is configured with a bad API key
    url = f"{litellm_proxy_url}/v1/chat/completions"
    payload = {
        "model": "invalid-nim",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    
    response = httpx.post(url, json=payload, timeout=20.0)
    assert response.status_code in [400, 401, 403], f"Expected auth error, got: {response.status_code} - {response.text}"
    print(f"\ninvalid-nim successfully returned auth error: {response.status_code}")

def test_bad_parameter_error(litellm_proxy_url):
    # We need at least one valid model to test parameter validation
    target_model = None
    if not should_skip("gemini-flash"):
        target_model = "gemini-flash"
    elif not should_skip("nvidia-nim"):
        target_model = "nvidia-nim"
    elif not should_skip("ollama-chat"):
        target_model = "ollama-chat"
        
    if not target_model:
        pytest.skip("No valid model credentials configured, skipping bad parameter test")

    url = f"{litellm_proxy_url}/v1/chat/completions"
    
    # Pass an invalid role which LiteLLM/Upstream must reject with a client error
    payload = {
        "model": target_model,
        "messages": [{"role": "not_a_real_role", "content": "Hello"}],
    }
    
    response = httpx.post(url, json=payload, timeout=20.0)
    # Expected parameter error (400 Bad Request or 422 Unprocessable Entity)
    assert response.status_code in [400, 422], f"Expected 400/422 Bad Request, got: {response.status_code} - {response.text}"
    print(f"\n{target_model} successfully returned parameter error: {response.status_code}")
