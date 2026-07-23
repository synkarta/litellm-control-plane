# Module Spec: Config Generator

## Purpose
The Config Generator module (`src/config/generator.py`) acts as the compiler bridging the control plane's SQLite state (inventory + policy + health) into a LiteLLM-compatible YAML configuration.

## Responsibilities
- Query the database to resolve which `Endpoints` belong to a target `Node`.
- Apply routing logic exclusions based on health (`ep_status`, `acc_status`) and manual overrides (`force-disabled`, `force-active`).
- Resolve secrets via the Doppler resolver.
- Resolve dynamic `api_base` URLs for self-hosted providers (e.g., Ollama, NIM).
- Map models to logical groups (e.g., `gemini-2.5-flash` mapped to `general-chat`).
- Output the fully resolved configuration payload (and optionally write to disk).

## Inputs and Outputs
- **Input**: `node_id` (string), active SQLite `Connection` object.
- **Output**: A Python dictionary matching the LiteLLM YAML schema (e.g., `{"model_list": [...], "litellm_settings": {...}}`).

## Invariants
- Endpoints or Accounts in `disabled`, `cooldown`, or `inactive` status MUST NOT appear in the generated config, unless `manual_override="force-active"` is applied on the endpoint (and the account is not completely disabled/inactive).
- Secrets must be securely resolved at generation time.
- Provider-specific prefixing rules must be applied (e.g., NIM models require the `openai/` prefix).

## Dependencies
- `src.registry.store` (for querying SQLite data).
- `src.secrets.doppler.DopplerResolver` (for securely resolving secrets and `api_base`).
- `yaml` (for serialization).

## Failure Modes & Handling
- **Secret Resolution Failure**: If a secret fails to resolve, the generator logs a warning and *skips* that specific endpoint, continuing with the rest of the configuration.
- **API Base Resolution Failure**: Similar to secrets, falls back gracefully.

## Observability Requirements
- Emit warnings if `force-active` is blocked by account-level disabling.
- Emit warnings if an endpoint is excluded due to secret resolution failure.

## Security Notes
- The resulting YAML dictionary contains RAW API keys. This payload must be handled carefully in memory and should only be written to disk transiently during rollout orchestration (where it is later applied).

## Validation Checklist
- [x] Generates valid LiteLLM `model_list` schema.
- [x] Respects node, endpoint, and account status flags.
- [x] Resolves and injects `api_base` for non-cloud endpoints correctly.
- [x] Applies provider prefixes appropriately.
- [x] Gracefully drops endpoints with unresolvable credentials without failing the entire batch.
