import os
import json
import time
import socket
import subprocess
import tempfile
import yaml
import httpx

# Helper to find a free port
def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def should_skip(model_name):
    if model_name == "ollama-chat":
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
    
    # Cloud providers checks
    env_var = "GEMINI_API_KEY" if model_name == "gemini-flash" else "NIM_API_KEY"
    env_val = os.getenv(env_var)
    if not env_val:
        if model_name == "nvidia-nim" and os.getenv("NVIDIA_API_KEY"):
            return False
        return True
    return False

def test_endpoint_capabilities(proxy_url, model_name):
    report = {
        "model_name": model_name,
        "status": "untested",
        "capabilities": {
            "chat": False,
            "streaming": False,
            "tool_calling": False,
        },
        "performance": {
            "avg_latency_seconds": None,
            "avg_ttft_seconds": None,
        },
        "errors": []
    }

    if should_skip(model_name):
        report["status"] = "skipped"
        return report

    url = f"{proxy_url}/v1/chat/completions"

    # 1. Test standard chat
    try:
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.0,
        }
        start = time.time()
        res = httpx.post(url, json=payload, timeout=15.0)
        latency = time.time() - start
        if res.status_code == 200:
            report["capabilities"]["chat"] = True
            report["performance"]["avg_latency_seconds"] = round(latency, 3)
            report["status"] = "verified"
        else:
            report["errors"].append(f"Chat failed with status {res.status_code}: {res.text}")
            report["status"] = "failed"
    except Exception as e:
        report["errors"].append(f"Chat error: {str(e)}")
        report["status"] = "failed"

    # 2. Test streaming chat
    try:
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "Say 'hello'"}],
            "stream": True,
            "temperature": 0.0,
        }
        start = time.time()
        ttft = None
        with httpx.stream("POST", url, json=payload, timeout=15.0) as r:
            if r.status_code == 200:
                for line in r.iter_lines():
                    if line.strip().startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        if ttft is None:
                            ttft = time.time() - start
                            break
                report["capabilities"]["streaming"] = True
                report["performance"]["avg_ttft_seconds"] = round(ttft, 3) if ttft else None
            else:
                report["errors"].append(f"Streaming failed with status {r.status_code}")
    except Exception as e:
        report["errors"].append(f"Streaming error: {str(e)}")

    # 3. Test Tool Calling
    try:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "Get the current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"}
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "What is the weather in Tokyo?"}],
            "tools": tools,
            "temperature": 0.0,
        }
        res = httpx.post(url, json=payload, timeout=15.0)
        if res.status_code == 200:
            data = res.json()
            message = data["choices"][0]["message"]
            if "tool_calls" in message:
                report["capabilities"]["tool_calling"] = True
            else:
                report["errors"].append("Tool calling test did not return tool_calls field")
        else:
            report["errors"].append(f"Tool calling failed with status {res.status_code}")
    except Exception as e:
        report["errors"].append(f"Tool calling error: {str(e)}")

    return report

def main():
    print("Starting Provider Compatibility Baseline Ingestion...")

    # Set up local proxy config
    port = get_free_port()
    proxy_url = f"http://127.0.0.1:{port}"
    
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

    # Start LiteLLM
    litellm_exe = os.path.join(".venv", "Scripts", "litellm.exe")
    if not os.path.exists(litellm_exe):
        litellm_exe = "litellm"
        
    cmd = [litellm_exe, "--config", config_path, "--port", str(port)]
    
    # Run the process
    log_file_path = os.path.join(temp_dir, "litellm_proxy.log")
    log_file = open(log_file_path, "w", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        env=env
    )

    # Poll /health
    connected = False
    for i in range(90):
        if process.poll() is not None:
            break
        try:
            res = httpx.get(f"{proxy_url}/health/readiness", timeout=1.0)
            if res.status_code == 200:
                connected = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not connected:
        process.terminate()
        log_file.close()
        with open(log_file_path, "r", encoding="utf-8") as f:
            logs = f.read()
        print(f"Error starting LiteLLM in time (90 retries). Logs:\n{logs}")
        return

    # Run tests for each model
    results = {}
    models_to_test = ["gemini-flash", "nvidia-nim", "ollama-chat"]
    for model in models_to_test:
        print(f"Testing capability of {model}...")
        report = test_endpoint_capabilities(proxy_url, model)
        results[model] = report
        print(f"Result for {model}: {report['status']} (chat: {report['capabilities']['chat']}, stream: {report['capabilities']['streaming']}, tools: {report['capabilities']['tool_calling']})")

    # Stop proxy
    process.terminate()
    try:
        process.wait(timeout=5)
    except Exception:
        process.kill()

    log_file.close()

    # Clean config
    try:
        os.remove(log_file_path)
        os.remove(config_path)
        os.rmdir(temp_dir)
    except Exception:
        pass

    # Save report
    report_path = os.path.join("tests", "provider_baseline", "baseline_report.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Baseline Compatibility Report saved to {report_path}")

if __name__ == "__main__":
    main()
