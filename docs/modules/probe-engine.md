# Probe Engine Specification

## Purpose
The Probe Engine runs scheduled and active checks against accounts and endpoints to determine if resources can transition out of `probe` or `degraded` status back to `active`.

## Responsibilities
- Execute synthetic API requests to upstream providers using the exact API Key defined in Doppler.
- Support low-cost, provider-specific probe templates (e.g. prompt chat completion with `max_tokens=1`).
- Classify outcomes (Success, 429, Auth Error, Timeout) and trigger corresponding State Machine transitions.
- Enforce check jitter and retry intervals to avoid hammering recovery targets.

## Inputs and Outputs
- **Inputs**:
  - Target resource check command (triggered by Cron scheduler or manual endpoint call).
- **Outputs**:
  - Request outcome sent to the Account State Machine.

## Invariants
- Probes must be mockable during testing to avoid calling real billing APIs.
- Probes must set a low connection timeout (e.g. 5 seconds) to avoid hanging.

## Dependencies
- DopplerResolver (for resolving secret reference values).
- `httpx.Client`.

## Validation Checklist
- [ ] Active probing of a healthy endpoint transitions it back to `active`.
- [ ] Probe failure keeps the endpoint in degraded or disabled state.
- [ ] In unit tests, real HTTP requests are completely mocked.
