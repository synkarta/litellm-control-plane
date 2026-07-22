import logging
import os
import re
import hashlib
import time
from typing import Dict, Optional, Tuple
import httpx

logger = logging.getLogger("doppler_resolver")

class DopplerResolver:
    def __init__(self, cache_ttl: float = 300.0, client: Optional[httpx.Client] = None):
        """
        doppler_resolver resolves references in the format: doppler://PROJECT/CONFIG/SECRET_NAME

        Args:
            cache_ttl: Time-to-live for cached secret dictionaries (in seconds)
            client: Optional httpx.Client instance for testing (caller owns its lifecycle)
        """
        self.cache_ttl = cache_ttl
        self._external_client = client is not None
        self.client = client or httpx.Client(timeout=10.0)
        # Cache format: token -> (fetch_time, Dict[secret_key, secret_val])
        self._cache: Dict[str, Tuple[float, Dict[str, str]]] = {}

    def close(self) -> None:
        """Explicitly close the underlying HTTP client if we own it."""
        if not self._external_client:
            self.client.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def parse_uri(self, uri: str) -> Tuple[str, str, str]:
        """
        Parse doppler://PROJECT/CONFIG/SECRET_NAME into (project, config, secret_name).
        Raises ValueError if format is invalid.
        """
        match = re.match(r"^doppler://([^/]+)/([^/]+)/([^/]+)$", uri)
        if not match:
            raise ValueError(
                f"Invalid Doppler secret URI: '{uri}'. Must match format: 'doppler://PROJECT/CONFIG/SECRET_NAME'"
            )
        return match.group(1), match.group(2), match.group(3)

    def _get_token(self, project: str, config: str) -> Optional[str]:
        """
        Look up Doppler service token in environment.
        Tries:
        1. DOPPLER_TOKEN_<PROJECT>_<CONFIG> (normalized to uppercase/underscores)
        2. DOPPLER_TOKEN
        """
        # Normalize PROJECT and CONFIG for env var matching
        norm_project = re.sub(r"[^A-Za-z0-9]", "_", project).upper()
        norm_config = re.sub(r"[^A-Za-z0-9]", "_", config).upper()
        env_var_name = f"DOPPLER_TOKEN_{norm_project}_{norm_config}"
        
        token = os.getenv(env_var_name)
        if token:
            return token
            
        return os.getenv("DOPPLER_TOKEN")

    def _fetch_secrets_from_doppler(self, token: str) -> Dict[str, str]:
        """
        Fetch flat JSON map of all secrets from Doppler configs download API.
        """
        url = "https://api.doppler.com/v3/configs/config/secrets/download"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        response = self.client.get(url, headers=headers)
        if response.status_code == 401:
            raise ValueError("Unauthorized: Invalid Doppler Service Token")
        elif response.status_code == 429:
            raise RuntimeError("Rate Limited: Doppler API rate limit exceeded")
        elif response.status_code != 200:
            raise RuntimeError(f"Doppler API returned unexpected status {response.status_code}: {response.text}")
            
        return response.json()

    def _get_secrets_with_cache(self, token: str) -> Dict[str, str]:
        """
        Gets secrets dict for token, utilizing caching.
        """
        now = time.time()
        cache_key = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if cache_key in self._cache:
            fetch_time, secrets = self._cache[cache_key]
            if now - fetch_time < self.cache_ttl:
                return secrets
                
        # Cache miss or expired
        secrets = self._fetch_secrets_from_doppler(token)
        self._cache[cache_key] = (now, secrets)
        return secrets

    def resolve(self, uri: str) -> str:
        """
        Resolve a Doppler secret reference.
        
        Fallback strategy on failure:
        If token resolution or HTTP fetch fails, attempts to read matching SECRET_NAME
        directly from the local environment variables. If missing, raises ValueError.
        """
        project, config, secret_name = self.parse_uri(uri)
        token = self._get_token(project, config)
        
        if not token:
            # Fallback to local environment directly
            local_val = os.getenv(secret_name)
            if local_val is not None:
                logger.warning(
                    f"No Doppler token found for project='{project}' config='{config}'. "
                    f"Falling back to local env var '{secret_name}'." 
                )
                return local_val
            raise ValueError(
                f"Could not resolve secret '{uri}': No Doppler token found "
                f"and local env var '{secret_name}' is unset."
            )
            
        try:
            secrets = self._get_secrets_with_cache(token)
            if secret_name in secrets:
                return secrets[secret_name]
            # Key not found in Doppler response — fallback to local env
            local_val = os.getenv(secret_name)
            if local_val is not None:
                logger.warning(
                    f"Secret '{secret_name}' not found in Doppler config for "
                    f"project='{project}' config='{config}'. Falling back to local env var."
                )
                return local_val
            raise ValueError(
                f"Secret key '{secret_name}' not found in resolved Doppler config "
                f"and local env var is unset."
            )
        except Exception as e:
            # On any Doppler resolution exception, try local env fallback
            local_val = os.getenv(secret_name)
            if local_val is not None:
                logger.warning(
                    f"Doppler resolution failed for '{uri}' (error: {e}). "
                    f"Falling back to local env var '{secret_name}'."
                )
                return local_val
            raise ValueError(
                f"Failed to resolve secret '{uri}' from Doppler: {e}. "
                f"Local env var fallback also failed."
            )
