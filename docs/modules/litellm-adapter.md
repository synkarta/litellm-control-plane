# Module Spec: LiteLLM Adapter

## Purpose
The LiteLLM Adapter module (`src/adapters/litellm_adapter.py`) serves as the strict operational boundary between the control plane and the LiteLLM proxy executing the requests. The control plane NEVER directly proxies user traffic; instead, it uses this adapter to orchestrate the internal configurations and identity objects within a running LiteLLM process.

## Responsibilities
- Provide a typed client for the LiteLLM Management API endpoints.
- Check the operational health / readiness of the target LiteLLM node.
- Manage Virtual Keys (`/key/generate`, `/key/update`, `/key/delete`) to link Consumer objects to LiteLLM's internal rate limiting and spend tracking capabilities.
- Provide a subprocess launcher (`start_subprocess`) for local development, CI/CD testing, and unified process lifecycle management during tests.

## Inputs and Outputs
- **Input**: LiteLLM proxy base URL, master API key, optional custom `httpx.Client`.
- **Output**: JSON payload responses translated to Python dictionaries representing Virtual Key details and health booleans.

## Invariants
- Must always pass the `Authorization: Bearer <master_key>` header for management API calls.
- Must not implement retry logic on 4xx/5xx API failures from LiteLLM, as those represent hard orchestration failures that should bubble up to the Rollout Orchestrator.

## Dependencies
- `httpx` for HTTP interaction with the LiteLLM proxy.
- `subprocess` for local process spawning.

## Failure Modes & Handling
- **Connection Timeout/Refused**: The LiteLLM node is down or inaccessible. Bubbles up as an exception that the health manager or orchestrator will catch.
- **Subprocess Startup Failure**: Returns standard error and terminates aggressively if the proxy does not become ready within 30 seconds.

## Observability Requirements
- Exceptions thrown must clearly state whether the failure was during key generation, update, or deletion.
- Standard out/err of the proxy process spawned locally must be captured and logged for debugging.

## Security Notes
- The Master Key is highly sensitive and is used exclusively by this adapter.
- The adapter does NOT handle the ingestion of callbacks or routing data; it strictly operates on the management API path.

## Validation Checklist
- [x] Correctly checks `/health/readiness`.
- [x] Calls `/key/generate` with proper model allow-lists and budget constraints.
- [x] Calls `/key/update` with correct payloads.
- [x] Calls `/key/delete` to cleanly revoke keys.
- [x] Reliably spawns and terminates a local LiteLLM proxy instance.
