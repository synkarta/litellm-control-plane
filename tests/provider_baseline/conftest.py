import os
import time
import socket
import subprocess
import tempfile
import yaml
import pytest
import httpx

# Helper to find a free port for LiteLLM proxy
def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

@pytest.fixture(scope="session")
def litellm_proxy_url():
    # If the user specified an external proxy, use it directly
    external_url = os.getenv("LITELLM_PROXY_URL")
    if external_url:
        print(f"\nUsing external LiteLLM Proxy: {external_url}")
        yield external_url
        return

    # Otherwise, spin up a local instance automatically
    port = get_free_port()
    proxy_url = f"http://127.0.0.1:{port}"
    print(f"\nStarting local LiteLLM Proxy on port {port}...")

    # Load credentials from environment
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    nim_key = os.getenv("NIM_API_KEY", os.getenv("NVIDIA_API_KEY", ""))
    ollama_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

    # Sanitize Ollama base URL if it ends with /api or /api/
    if ollama_base.endswith("/api"):
        ollama_base = ollama_base[:-4]
    elif ollama_base.endswith("/api/"):
        ollama_base = ollama_base[:-5]

    # Collect keys to check (OLLAMA_API_KEY, then OLLAMA_API_BKUP_KEY, then anonymous)
    ollama_keys = []
    if os.getenv("OLLAMA_API_KEY"):
        ollama_keys.append(os.getenv("OLLAMA_API_KEY"))
    if os.getenv("OLLAMA_API_BKUP_KEY"):
        ollama_keys.append(os.getenv("OLLAMA_API_BKUP_KEY"))
    if not ollama_keys:
        ollama_keys.append("")

    # Query first working Ollama model dynamically
    ollama_model = None
    ollama_key = ""
    for key in ollama_keys:
        headers = {}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            response = httpx.get(f"{ollama_base}/api/tags", headers=headers, timeout=5.0)
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
                        res = httpx.post(f"{ollama_base}/api/generate", json=test_payload, headers=headers, timeout=5.0)
                        if res.status_code == 200:
                            ollama_model = m_name
                            ollama_key = key
                            break
                    except Exception:
                        pass
            if ollama_model:
                break
        except Exception:
            pass

    if not ollama_model:
        ollama_model = "llama3.2" # default fallback
        ollama_key = os.getenv("OLLAMA_API_KEY", "")

    # Generate a temporary config.yaml
    config_data = {
        "model_list": [
            {
                "model_name": "gemini-flash",
                "litellm_params": {
                    "model": "gemini/gemini-2.5-flash",
                    "api_key": gemini_key,
                }
            },
            {
                "model_name": "nvidia-nim",
                "litellm_params": {
                    "model": "openai/meta/llama-3.1-8b-instruct",
                    "api_base": "https://integrate.api.nvidia.com/v1",
                    "api_key": nim_key,
                }
            },
            {
                "model_name": "ollama-chat",
                "litellm_params": {
                    "model": f"ollama/{ollama_model}",
                    "api_base": ollama_base,
                    "api_key": ollama_key,
                }
            },
            {
                "model_name": "invalid-gemini",
                "litellm_params": {
                    "model": "gemini/gemini-2.5-flash",
                    "api_key": "bad-key-xyz-123",
                }
            },
            {
                "model_name": "invalid-nim",
                "litellm_params": {
                    "model": "openai/meta/llama-3.1-8b-instruct",
                    "api_base": "https://integrate.api.nvidia.com/v1",
                    "api_key": "bad-key-xyz-123",
                }
            }
        ],
        "litellm_settings": {
            "drop_params": True
        }
    }

    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, "litellm_config.yaml")
    with open(config_path, "w") as f:
        yaml.safe_dump(config_data, f)

    # Start LiteLLM proxy subprocess
    # In Windows, we run litellm.exe inside the virtual environment
    litellm_exe = os.path.join(".venv", "Scripts", "litellm.exe")
    if not os.path.exists(litellm_exe):
        litellm_exe = "litellm" # fallback to path

    cmd = [litellm_exe, "--config", config_path, "--port", str(port)]
    
    # Run the process
    log_file_path = os.path.join(temp_dir, "litellm_proxy.log")
    log_file = open(log_file_path, "w", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("LITELLM_MASTER_KEY", None)
    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        env=env
    )

    # Poll /health or /ping until healthy
    health_url = f"{proxy_url}/health/readiness"
    retries = 90
    connected = False
    
    # Wait for the service to start
    for i in range(retries):
        if process.poll() is not None:
            # Subprocess died
            log_file.close()
            with open(log_file_path, "r", encoding="utf-8") as f:
                logs = f.read()
            raise RuntimeError(f"LiteLLM proxy failed to start. exit_code={process.returncode}\nLogs:\n{logs}")
        try:
            response = httpx.get(health_url, timeout=1.0)
            if response.status_code == 200:
                connected = True
                break
        except httpx.RequestError:
            pass
        time.sleep(0.5)

    if not connected:
        process.terminate()
        log_file.close()
        with open(log_file_path, "r", encoding="utf-8") as f:
            logs = f.read()
        raise RuntimeError(f"LiteLLM proxy failed to start in time (90 retries). Logs:\n{logs}")

    print(f"LiteLLM Proxy is healthy and running at {proxy_url}")
    
    yield proxy_url

    # Teardown: Stop the process
    print("\nShutting down local LiteLLM Proxy...")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()

    log_file.close()

    # Clean up temp file
    try:
        os.remove(log_file_path)
        os.remove(config_path)
        os.rmdir(temp_dir)
    except Exception:
        pass
