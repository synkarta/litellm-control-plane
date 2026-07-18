import os
import time
import httpx
import pytest

MODELS = {
    "gemini-flash": {
        "env_var": "GEMINI_API_KEY",
        "skip_reason": "GEMINI_API_KEY not set"
    },
    "nvidia-nim": {
        "env_var": "NIM_API_KEY",
        "skip_reason": "NIM_API_KEY (or NVIDIA_API_KEY) not set"
    },
    "ollama-chat": {
        "env_var": "OLLAMA_API_BASE",
        "skip_reason": "OLLAMA_API_BASE not set (defaulting to check if ollama is running)"
    }
}

# Helper to check if a specific model is ready to be tested
def should_skip(model_name):
    if model_name == "ollama-chat":
        # Check if ollama is running locally and has any models loaded
        base_url = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
        if base_url.endswith("/api"):
            base_url = base_url[:-4]
        elif base_url.endswith("/api/"):
            base_url = base_url[:-5]
        
        # Collect keys to check
        ollama_keys = []
        if os.getenv("OLLAMA_API_KEY"):
            ollama_keys.append(os.getenv("OLLAMA_API_KEY"))
        if os.getenv("OLLAMA_API_BKUP_KEY"):
            ollama_keys.append(os.getenv("OLLAMA_API_BKUP_KEY"))
        if not ollama_keys:
            ollama_keys.append("")

        for key in ollama_keys:
            headers = {}
            if key:
                headers["Authorization"] = f"Bearer {key}"
                
            try:
                response = httpx.get(f"{base_url}/api/tags", headers=headers, timeout=5.0)
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    for m_item in models:
                        m_name = m_item["name"]
                        test_payload = {
                            "model": m_name,
                            "prompt": "hi",
                            "stream": False,
                            "options": {"num_predict": 1}
                        }
                        try:
                            res = httpx.post(f"{base_url}/api/generate", json=test_payload, headers=headers, timeout=5.0)
                            if res.status_code == 200:
                                return False # Found a working model and key combination! Do not skip.
                        except Exception:
                            pass
            except Exception:
                pass
        return True
    
    # For cloud providers, check key presence
    env_val = os.getenv(MODELS[model_name]["env_var"])
    if not env_val:
        # Also check NVIDIA_API_KEY for nim
        if model_name == "nvidia-nim" and os.getenv("NVIDIA_API_KEY"):
            return False
        return True
    return False

@pytest.mark.parametrize("model_name", MODELS.keys())
def test_chat_non_streaming(litellm_proxy_url, model_name):
    if should_skip(model_name):
        pytest.skip(f"Skipping {model_name}: {MODELS[model_name]['skip_reason']}")

    url = f"{litellm_proxy_url}/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Say hello in exactly one word."}],
        "temperature": 0.0,
    }

    start_time = time.time()
    response = httpx.post(url, json=payload, timeout=20.0)
    latency = time.time() - start_time

    assert response.status_code == 200, f"Failed: {response.text}"
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    content = data["choices"][0]["message"]["content"].strip()
    assert len(content) > 0
    
    print(f"\nModel {model_name} (Non-Streaming) Latency: {latency:.2f}s, Response: {content}")

@pytest.mark.parametrize("model_name", MODELS.keys())
def test_chat_streaming(litellm_proxy_url, model_name):
    if should_skip(model_name):
        pytest.skip(f"Skipping {model_name}: {MODELS[model_name]['skip_reason']}")

    url = f"{litellm_proxy_url}/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Count from 1 to 5."}],
        "stream": True,
        "temperature": 0.0,
    }

    start_time = time.time()
    ttft = None
    chunks = []

    with httpx.stream("POST", url, json=payload, timeout=20.0) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if not line.strip():
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                if ttft is None:
                    ttft = time.time() - start_time
                chunks.append(data_str)

    total_latency = time.time() - start_time
    assert len(chunks) > 0
    assert ttft is not None

    print(f"\nModel {model_name} (Streaming) TTFT: {ttft:.2f}s, Total Latency: {total_latency:.2f}s")
