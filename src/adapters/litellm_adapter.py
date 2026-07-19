import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

class LiteLLMAdapter:
    def __init__(self, proxy_url: str, master_key: str, client: Optional[httpx.Client] = None):
        """
        Adapter to interface with a running LiteLLM Proxy.
        """
        self.proxy_url = proxy_url.rstrip("/")
        self.master_key = master_key
        self.client = client or httpx.Client(timeout=15.0)

    def check_health(self) -> bool:
        """
        Queries the LiteLLM Proxy readiness endpoint.
        """
        url = f"{self.proxy_url}/health/readiness"
        try:
            response = self.client.get(url)
            return response.status_code == 200
        except httpx.RequestError:
            return False

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.master_key}",
            "Content-Type": "application/json"
        }

    def generate_key(
        self,
        models: List[str],
        metadata: Dict[str, Any],
        max_budget: Optional[float] = None,
        rate_limit_rpm: Optional[int] = None,
        rate_limit_tpm: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Call /key/generate to issue a new virtual key.
        Returns the generated response JSON containing the new key.
        """
        url = f"{self.proxy_url}/key/generate"
        payload: Dict[str, Any] = {
            "models": models,
            "metadata": metadata
        }
        if max_budget is not None:
            payload["max_budget"] = max_budget
        if rate_limit_rpm is not None:
            payload["rate_limit_rpm"] = rate_limit_rpm
        if rate_limit_tpm is not None:
            payload["rate_limit_tpm"] = rate_limit_tpm

        response = self.client.post(url, json=payload, headers=self._get_headers())
        if response.status_code != 200:
            raise RuntimeError(f"Failed to generate LiteLLM key: {response.text}")
        return response.json()

    def update_key(
        self,
        key: str,
        models: List[str],
        metadata: Dict[str, Any],
        max_budget: Optional[float] = None,
        rate_limit_rpm: Optional[int] = None,
        rate_limit_tpm: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Call /key/update to update limits on an existing virtual key.
        """
        url = f"{self.proxy_url}/key/update"
        payload: Dict[str, Any] = {
            "key": key,
            "models": models,
            "metadata": metadata
        }
        if max_budget is not None:
            payload["max_budget"] = max_budget
        if rate_limit_rpm is not None:
            payload["rate_limit_rpm"] = rate_limit_rpm
        if rate_limit_tpm is not None:
            payload["rate_limit_tpm"] = rate_limit_tpm

        response = self.client.post(url, json=payload, headers=self._get_headers())
        if response.status_code != 200:
            raise RuntimeError(f"Failed to update LiteLLM key: {response.text}")
        return response.json()

    def delete_key(self, key: str) -> bool:
        """
        Call /key/delete to revoke a virtual key.
        """
        url = f"{self.proxy_url}/key/delete"
        payload = {"keys": [key]}
        response = self.client.post(url, json=payload, headers=self._get_headers())
        return response.status_code == 200

    @staticmethod
    def start_subprocess(
        config_path: str,
        port: int,
        log_filepath: Optional[str] = None
    ) -> Tuple[subprocess.Popen, str]:
        """
        Spawns a local LiteLLM Proxy process for testing / local development.
        """
        proxy_url = f"http://127.0.0.1:{port}"
        
        # Check standard paths for LiteLLM executable (Windows vs Linux/macOS)
        litellm_exe = os.path.join(".venv", "Scripts", "litellm.exe")
        if not os.path.exists(litellm_exe):
            litellm_exe = os.path.join(".venv", "bin", "litellm")
        if not os.path.exists(litellm_exe):
            litellm_exe = "litellm"
            
        cmd = [litellm_exe, "--config", config_path, "--port", str(port)]
        
        if log_filepath:
            log_file = open(log_filepath, "w", encoding="utf-8")
        else:
            log_file = subprocess.DEVNULL
            
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )
        
        # Poll readiness endpoint
        health_url = f"{proxy_url}/health/readiness"
        connected = False
        for _ in range(60): # up to 30 seconds wait
            if process.poll() is not None:
                if log_filepath:
                    log_file.close()
                    with open(log_filepath, "r", encoding="utf-8") as f:
                        logs = f.read()
                else:
                    logs = "No logfile provided."
                raise RuntimeError(f"LiteLLM proxy failed to start. exit_code={process.returncode}\nLogs:\n{logs}")
            try:
                # Direct check
                with httpx.Client(timeout=1.0) as temp_client:
                    res = temp_client.get(health_url)
                    if res.status_code == 200:
                        connected = True
                        break
            except Exception:
                pass
            time.sleep(0.5)
            
        if not connected:
            process.terminate()
            if log_filepath:
                log_file.close()
            raise TimeoutError("LiteLLM proxy failed to become ready in time.")
            
        return process, proxy_url
