# Health Manager Specification

## Purpose
The Health Manager aggregates health state across separate dimensions (Nodes, Accounts, and Endpoints) rather than computing a single opaque metric. This keeps individual resource issues isolated.

## Responsibilities
- Monitor and cache current status for Nodes, Accounts, and Endpoints.
- Expose endpoints to query health state summaries.
- Serve as the query interface for policy routing to determine resource eligibility.
- List active and historical incidents for operators.

## Inputs and Outputs
- **Inputs**:
  - Webhook failure/success signals via LiteLLM API callbacks.
  - Periodic active checking results from the Probe Engine.
  - State changes driven by the Account State Machine.
- **Outputs**:
  - Aggregated health state dict for API/UI.
  - Eligibility queries for configuration generation.

## Invariants
- An Endpoint cannot be considered `active` if its corresponding Account is `cooldown` or `disabled`.
- A Node's health status must reflect the aggregation of its endpoints, but account-specific failures must never mark a whole Node as unhealthy.

## Dependencies
- SQLite database (`endpoints`, `accounts`, `nodes`, and `incidents` tables).

## Failure Modes
- **Database lock/contention**: Ingestion of concurrent callbacks must use transaction-level safety to prevent locks.
- **Out of sync states**: The manager relies on drift reconciliation to recover states if callbacks fail to arrive.

## Observability Requirements
- Metrics for error rates and current cooldown counts.
- Log of all health status updates and operator overrides.

## Security Notes
- Diagnostic endpoints like `GET /health/summary` and `GET /health/incidents` require `X-Admin-API-Key` authentication.

## Out-of-Scope Items
- Gateway-level request retries (handled entirely by LiteLLM).

## Validation Checklist
- [x] Active endpoints are returned correctly in health summaries.
- [x] Blocked endpoints due to account status are excluded correctly.
- [x] Incident list returns actual historic logs.
- [x] Incidents can be filtered by target_type, target_id, state_to.
