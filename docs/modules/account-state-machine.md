# Account State Machine Specification

## Purpose
The Account State Machine manages status transitions for Accounts and Endpoints based on failures or operator requests.

## Responsibilities
- Track error thresholds for rate limits, key auth, timeouts, and network issues.
- Transition Account and Endpoint states cleanly.
- Set/clear cooldown timers.
- Log transition records in database and system outputs.

## Inputs and Outputs
- **Inputs**:
  - Request outcome (success/error, status code, error details) from events or probes.
  - Operator override command.
- **Outputs**:
  - Transition events logged in `incidents` table.
  - Transition messages in standard logger format.

## Invariants
- **Key Logging Format**:
  Every transition must log to the standard Python logging stream:
  `[Entity] [ID] State Transition: OLD_STATE -> NEW_STATE (Reason: ...)`
- **Auto-Recovery**: Cooldown items are eligible for transition to `probe` state after `cooldown_until` expires.
- **Immediate Disabling**: Any Authentication Error (401/403) must instantly transition the target Account to `disabled`.

## States
- `active`: Resource is fully healthy and routing traffic.
- `degraded`: Resource is experiencing elevated timeout or 5xx rates.
- `cooldown`: Resource has hit rate limits (429) or transient faults. Temporarily excluded.
- `disabled`: Key or credentials are bad, or manually turned off. Excluded permanently until reset.
- `probe`: Testing state. Actively probed with synthetic payloads.
- `recovered`: Transient state indicating resource has passed checks and is returning to `active`.

## Thresholds & Triggers
- **Rate Limit (429)**: Instant transition to `cooldown` for 30 seconds.
- **Auth Failure (401/403)**: Instant transition to `disabled`.
- **Timeout / 5xx Connection Error**:
  - Increments `failure_count`.
  - If `failure_count` >= 3, transition to `degraded`.

## Dependencies
- SQLite database (`accounts` and `endpoints` tables).

## Out-of-Scope Items
- Client-side virtual key status management.

## Validation Checklist
- [x] 429 triggers cooldown and updates `cooldown_until`.
- [x] 401 triggers disabled state on both endpoint and account.
- [x] Timeout increments failure count and triggers degraded state at threshold.
- [x] Custom format log is printed to console on transition.
- [x] Cooldown cannot be exited by a success callback; only reconcile+probe may exit it.
- [x] 429/5xx failures are endpoint-scoped; account is only affected by auth errors (401/403).
- [x] All state transitions produce audit log entries.
