# Testing Strategy

This document defines the validation hierarchy and expectations for the `litellm-control-plane` project. The testing strategy enforces reliability across routing policies, health state management, configuration generation, and upstream provider consistency.

## 1. Unit Testing
Located in `tests/unit/`.

**Scope:**
- Isolated module logic (e.g., config generation logic, policy engine evaluation, doppler token parsing).
- Core state mutations in `sqlite3`.

**Rules:**
- Must not make external network requests (Mock HTTP clients where necessary).
- Must use an ephemeral SQLite file (or in-memory DB) to validate actual SQL logic, rather than mocking the database adapter.
- Run via `pytest tests/unit/`.

## 2. Integration Testing
Located in `tests/integration/`.

**Scope:**
- End-to-end API workflows (e.g., orchestrator initiating a rollout, modifying registry resources, and handling callback events).
- Simulates interactions between the Control Plane, the `LiteLLMAdapter`, and the `ConfigGenerator`.

**Rules:**
- Requires spawning a local test instance of LiteLLM (via `LiteLLMAdapter.start_subprocess`).
- Must assert the exact state of the generated YAML configuration and the corresponding virtual keys.

## 3. Provider Baseline Testing
Located in `tests/provider_baseline/`.

Because the Control Plane dynamically routes traffic based on presumed provider capabilities (e.g., tool calling, streaming), we must empirically validate that providers actually support these capabilities behind the LiteLLM proxy before allowing them in production.

**Scope:**
- Real network requests routed through a real LiteLLM instance to real upstream endpoints.
- Validates structural error handling (e.g., guaranteeing a 400/422 on invalid parameters rather than relying on inconsistent provider-specific `temperature` limits).
- Checks payload compatibility for chat, streaming, and embeddings.

**Rules:**
- Must be executed sequentially (no parallelization) to avoid aggressive rate limiting.
- Must not mutate the control plane's SQLite state.

## 4. Failure Injection & Chaos
Located in `tests/failure_injection/`.

**Scope:**
- Validates the Health Manager's state machine transitions.
- Simulates floods of 429 (Rate Limit), 401 (Auth Failure), and 5xx (Timeouts).

**Rules:**
- Ensures the control plane properly demotes endpoints from `active` -> `degraded` -> `cooldown`.
- Verifies that `rollback` functionality triggers correctly when an orchestrated rollout fails canary validation.
- Verifies that orphaned virtual keys are aggressively cleaned up during reconciliation (`POST /rollout/reconcile`).
