# Secrets Policy & Doppler Integration

This document defines how API keys and sensitive tokens are managed within `litellm-control-plane`. To maintain least-privilege security and eliminate accidental secret leakage, **raw secrets are never stored in the control plane's database or codebase.**

Instead, the control plane uses **Secret References** resolved dynamically at runtime using [Doppler](https://doppler.com).

## 1. Secret Reference Format

All API keys associated with `Account` objects must be specified as Doppler URIs in the format:
`doppler://<PROJECT>/<CONFIG>/<SECRET_NAME>`

For example:
`doppler://litellm-infra/prd_us/OPENAI_API_KEY`

This format allows the control plane to clearly map an account's credential to a specific environment and scope.

## 2. Doppler Token Resolution

The control plane (`src/secrets/doppler.py`) acts as the secure resolver. To access Doppler secrets, the control plane host must be provided with Doppler Service Tokens.

### Token Discovery Order
When resolving a secret reference, the system looks for Service Tokens in the environment in the following order:

1. **Config-Scoped Token (Preferred)**
   `DOPPLER_TOKEN_<PROJECT>_<CONFIG>`
   *Example: `DOPPLER_TOKEN_LITELLM_INFRA_PRD_US`*
   Use this approach in production to ensure the control plane only has access to the precise configurations it needs to govern that specific node or region.

2. **Global Fallback Token**
   `DOPPLER_TOKEN`
   *Example: Standard workspace fallback.*
   Primarily used for local development or simplified single-node setups.

## 3. Local Environment Fallback

To support local testing and CI/CD pipelines without requiring a live Doppler connection, the resolver implements a secure fallback mechanism:

If token resolution fails, the Doppler API request fails (e.g., rate limit, network timeout), or the specific secret key is not found in the downloaded config, the resolver will attempt to read the `SECRET_NAME` directly from the **local machine's environment variables**.

*Example: If `doppler://litellm-infra/prd/ANTHROPIC_KEY` fails, the system will fall back to reading `os.getenv("ANTHROPIC_KEY")`.*

A warning will be emitted to the operational logs whenever a fallback occurs.

## 4. Caching and Expiration

To minimize network latency and avoid hitting Doppler's API rate limits during mass rollout reconciliation, resolved secrets are cached in memory.

- **Cache Strategy**: In-memory dictionary mapped by the SHA-256 hash of the Doppler Service Token.
- **Cache TTL**: 300 seconds (5 minutes). 

## 5. Security Rules

- **No Persistence**: The control plane SQLite database must only store the `doppler://` URI strings.
- **No Exporting**: Generated LiteLLM configurations must inject secrets via OS environment variables (which LiteLLM natively resolves) OR the control plane orchestrator injects them ephemerally during apply; secrets must not be written to persistent YAML files on disk.
- **Least Privilege**: Production environments (`prd`) must not share service tokens with staging (`stg`) or testing (`tst`) environments. Service tokens should be strictly scoped using Doppler's access policies.
