# AI Development Rules — litellm-control-plane

This document governs coding style, architectural boundaries, and safety constraints for all AI and human developers working on the LiteLLM Control Plane.

## 1. Core Principles

*   **Spec-Before-Implementation**: Never write code for a module or endpoint without verifying that its specification exists under `docs/modules/` or `docs/api-contract.md`. If a specification is missing, create it first and obtain user approval.
*   **Surgical Changes**: Modify only the code necessary to solve the issue or implement the spec. Avoid unrelated refactoring or "cleanups."
*   **English-Only Persistent Artifacts**: All code comments, docstrings, variable names, database schemas, commit messages, and permanent documentation must be in **English**. (Chat interactions remain in Simplified Chinese).
*   **No Raw Secrets**: Secrets must never be committed to Git, logged in output console, or saved directly in the persistence database. Use Doppler references.

---

## 2. Code Organization & Patterns

*   **Python Target Version**: `>=3.12`.
*   **Frameworks**:
    *   **FastAPI** for API endpoints.
    *   **Pydantic v2** for schemas and validation.
    *   **SQLAlchemy** (or raw SQL queries via standard sqlite3 for MVP) for persistence. Keep database access isolated in the `src/state/` or `src/audit/` directories.
*   **Package Structure**:
    *   Place package files strictly in `src/litellm_control_plane/` (configured via hatchling packaging in `pyproject.toml`).
    *   Separate logical domains clearly into their respective directories under `src/` (e.g. `src/adapters/`, `src/policy/`, `src/health/`).
*   **Logging**:
    *   Use the standard Python `logging` library.
    *   Log messages must be formatted to exclude sensitive data (API keys, JWT bodies, Doppler tokens).
    *   Every state machine transition must log: `[Entity] [ID] State Transition: OLD_STATE -> NEW_STATE (Reason: ...)`

---

## 3. Prohibited Patterns

*   **No Direct Secret Storage**: Storing raw API keys, bearer tokens, or plain text database passwords in python constants, env variables, or the database is strictly forbidden.
*   **No Parallel Request Path Gateways**: Do not write HTTP routers that intercept and forward actual OpenAI completions requests. The control plane must not sit in the user request path. It only controls config and virtual keys.
*   **No Speculative Features**: Do not write abstractions for "future extension." Implement only the requirements defined in the active milestone specs.
*   **No Wildcard Imports**: Avoid `from module import *`.

---

## 4. Test Requirements

All new features must be accompanied by tests under the `tests/` directory:
*   **Unit Tests (`tests/unit/`)**: Written with `pytest`. Mock external APIs (Doppler, LiteLLM Admin API, Tailscale) completely. Unit tests must not depend on network calls or external state.
*   **Integration Tests (`tests/integration/`)**: Validate interactions between registries, configuration generation, and adapter layers using local SQLite mock instances.
*   **Provider Baselines (`tests/provider_baseline/`)**: Test suites designed to run against mock LiteLLM instances to check endpoint features (streaming, tool-calling, embeddings).
*   **Execution**: Run tests using `pytest` before proposing code changes. Ensure the test coverage does not drop.

---

## 5. Doppler and Secrets Scoping

*   Secrets are resolved by environment (`tst`, `stg`, `prd`).
*   Config generators must scope the Doppler Service Token to the narrowest target possible (e.g. region or node config branches) rather than requesting root/global project secrets.
*   Secrets loading code must raise descriptive validation errors if a token is expired or missing required keys, but must never dump the token string to standard output or error logs.

---

## 6. PR Evidence & Commit Messages

*   **Commit Messages**: Keep messages short, descriptive, and written in English (e.g., `feat(registry): add provider capabilities schema`).
*   **PR/Walkthrough Evidence**: Provide a summary of:
    1.  Changes made.
    2.  Test command run and its stdout output.
    3.  How rollback was validated (if modifying configuration generators or rollout handlers).
