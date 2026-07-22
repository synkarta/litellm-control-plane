# Event Ingestion Specification

## Purpose
The Event Ingestion module receives and processes API usage logs (successes, failures, latency, token usage) forwarded by LiteLLM proxy nodes.

## Responsibilities
- Expose a POST API endpoint `/events/callback`.
- Validate authenticity of calls via `X-Admin-API-Key`.
- Deduplicate callback logs using the unique request `id` to avoid double-processing.
- Extract `endpoint_id`, `account_id`, and `node_id` from the standard logging payload's metadata.
- Dispatch failure signals to the State Machine.

## Inputs and Outputs
- **Inputs**:
  - `POST /events/callback` HTTP request containing LiteLLM standard logging payload JSON array.
- **Outputs**:
  - Direct state machine trigger commands.
  - Success/Failure API response status.

## Payload Parsing Rules
- Inspect array elements. For each entry:
  - Verify if request `id` is already logged (avoid double-failover loops).
  - Extract metadata block: `metadata.endpoint_id`, `metadata.account_id`, `metadata.node_id`.
  - If a failure is indicated:
    - Identify status code / error type.
    - If `status_code` is 429 -> Trigger rate limit transition.
    - If `status_code` is 401 or 403 -> Trigger auth failure transition.
    - Else (timeout, connection issue, 5xx) -> Trigger timeout transition.

## Invariants
- Webhook endpoints must respond with `200 OK` quickly. Async background processing is preferred if parsing is slow.
- Replay protection must maintain a short-lived cache of processed request IDs (e.g. 5 minutes or SQLite checked) to prevent processing duplicates.

## Dependencies
- Fast API router, sqlite3 database.

## Validation Checklist
- [ ] Endpoint `/events/callback` is reachable and authenticated.
- [ ] Empty metadata is handled gracefully without crashing.
- [ ] Parsed 429 triggers cooldown state machine flow.
- [ ] Duplicate event is ignored.
