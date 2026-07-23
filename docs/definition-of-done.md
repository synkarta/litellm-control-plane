# Definition of Done

This document establishes the completion criteria for all features, modules, and API endpoints developed for `litellm-control-plane`. It guarantees that all code merged into the mainline adheres to the strict governance and operational reliability rules outlined in the project's strategy.

No pull request should be approved or merged unless the following checklist is fully satisfied.

## 1. Documentation Requirements
- [ ] **Specs First**: The module or feature must be backed by an existing module spec (in `docs/modules/`). If the spec was modified during implementation, the markdown file must be updated.
- [ ] **Architecture Records**: If the change altered control-plane boundaries or major design patterns, a new ADR (in `docs/adr/`) must be written and approved.
- [ ] **API Contract**: Any new endpoints, schemas, or query parameters must be documented in `docs/api-contract.md`.
- [ ] **Data Model**: If new state entities or properties were added, they must be documented in `docs/data-model.md`.

## 2. Testing & Validation Requirements
- [ ] **Unit Tests**: Offline unit tests must cover the core logic (in `tests/unit/`).
- [ ] **Provider Baseline**: If a new capability or endpoint requirement is introduced, it must be validated across providers in the `tests/provider_baseline/` suite.
- [ ] **Failure Injection**: The code must handle simulated failures gracefully (e.g., 429 floods, timeouts, missing secrets) as defined in the test strategy.
- [ ] **No Mocking of SQLite**: Database operations must be tested against a temporary SQLite file, not via Python `Mock` objects, to ensure valid SQL execution.

## 3. Observability & Audit Requirements
- [ ] **Audit Trail**: Every change to the registry or policy state must append a record via the `audit` module, capturing the actor, action, and diff.
- [ ] **Metrics**: Operations affecting routing, health state, or external calls must emit or update Prometheus metrics (in `src/metrics/`).
- [ ] **Incident Timeline**: State transitions to `degraded` or `cooldown` must generate an incident entry.

## 4. Rollout & Rollback Reliability
- [ ] **Versioned State**: Modifications to how config is generated must not break drift detection.
- [ ] **Rollback Capability**: The orchestrator must be capable of reverting any newly introduced LiteLLM config format back to the previous version without manual intervention.
- [ ] **Non-destructive Reconciliation**: Reconciliation runs must not forcefully restart nodes unless absolutely necessary and proven safe.

## 5. Security & Secrets Requirements
- [ ] **No Raw Secrets**: The code must NEVER log, expose via API, or persist raw API keys or secrets to the database. All secrets must remain as `doppler://` references.
- [ ] **Least Privilege**: The code must not elevate permissions globally if a node-scoped or config-scoped permission suffices.

## Acceptance Evidence
A valid PR must include in its description:
1. Links to the updated documentation.
2. Output of a successful local test run (`pytest`).
3. If applicable, an example of the newly generated LiteLLM config payload demonstrating the change.
