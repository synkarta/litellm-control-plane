# Module Spec: Doppler Integration

## Purpose
The Doppler Integration module (`src/secrets/doppler.py`) acts as the single secure resolver for API keys and sensitive tokens. It ensures that the control plane can securely fetch credentials needed by endpoints without ever storing them in the control plane's local database.

## Responsibilities
- Parse Doppler URI strings (`doppler://<PROJECT>/<CONFIG>/<SECRET_NAME>`).
- Discover appropriate Doppler Service Tokens from the environment using a hierarchical fallback mechanism (`DOPPLER_TOKEN_<PROJECT>_<CONFIG>` -> `DOPPLER_TOKEN`).
- Authenticate and fetch flat JSON payloads from the Doppler API (`/v3/configs/config/secrets/download`).
- Provide an in-memory caching layer mapped by the SHA-256 hash of the service token to reduce API rate limit exhaustion and lower latency.
- Handle failures by gracefully falling back to local environment variables.

## Inputs and Outputs
- **Input**: A secret reference URI (e.g., `doppler://litellm-infra/prd_us/OPENAI_API_KEY`).
- **Output**: The plain text secret string (e.g., `sk-...`).

## Invariants
- Raw secrets must never be logged or printed to the console.
- Caching must not exceed the TTL (default 300 seconds).
- The resolver must securely hash the service token before using it as a cache key.

## Dependencies
- `httpx` for HTTP requests to the Doppler API.
- Local `os.getenv` for fallback and token discovery.

## Failure Modes & Handling
- **401 Unauthorized**: Handled by falling back to the local environment variables.
- **429 Rate Limited**: Handled by falling back to the local environment variables.
- **Token Missing**: Handled by attempting a direct read of the `SECRET_NAME` from the local environment.

## Observability Requirements
- Emit warnings via the `doppler_resolver` logger when falling back to local environment variables.
- Log failures in token resolution securely (without logging the token itself).

## Security Notes
- Service tokens must be treated as highly sensitive.
- The cache dictionary lives in memory and is cleared upon application restart.
- The `DOPPLER_TOKEN_*` environment variables should be injected by the deployment platform securely (e.g., via Kubernetes secrets or systemd env files).

## Validation Checklist
- [x] Correctly parses standard Doppler URIs.
- [x] Rejects malformed URIs.
- [x] Correctly discovers specific vs global tokens.
- [x] Successfully caches and expires cached results.
- [x] Successfully falls back to local environment variables on HTTP errors or missing tokens.
