# LiteLLM Control Plane

`litellm-control-plane` is an external control plane for LiteLLM-based AI infrastructure. It governs resource inventory, account state lifecycle, routing policy eligibility, secret scoping, and configuration rollouts.

LiteLLM itself remains the request-path execution gateway (translating providers, handling virtual keys, quotas, budgets, retries, and request-level fallback/cooldown routing). The control plane decides **what config should exist** and **what resources are eligible**, and then drives LiteLLM with those decisions.

## Goals
- **Multi-Node & Multi-Region Support**: Govern multi-node, multi-provider, multi-account, and multi-region topologies from a single control plane.
- **Unified Inventory**: Keep structured registries for Nodes, Providers, Accounts, Models, and concrete Endpoints.
- **Least-Privilege Secrets**: Integrate with Doppler for environment-scoped and node-scoped secrets using metadata references.
- **Policy-Based Governance**: Filter candidate endpoints using consumer identity, tasks, and compliance metadata.
- **Controlled Rollouts & Rollback**: Validate configurations, perform canary rollouts, and automatically roll back on failure.
- **Failover & Cooldowns**: Track long-horizon account/endpoint health separately from LiteLLM's fast request-path retries.

## Non-Goals
- Not a replacement for LiteLLM's OpenAI-compatible gateway.
- Not a duplicate of LiteLLM's per-request retry, fallback, or routing mechanisms.
- Not a financial ledger (spend logs are used as operational signals, not accounting truth).
- Not a secret vault (secrets stay in Doppler).

The control plane acts as a service directory and health governor, coordinating multiple stateless LiteLLM nodes:

```text
               1. Query Active Node / Resolve Endpoint
      ┌──────────────────────────────────────────────────┐
      │                                                  │
      ▼                                                  │
+──────────────+                                  +────────────────────────+
| Applications | ◄────────────────────────────────| litellm-control-plane  |
|  (Consumers) |     2. Return Healthy Node IP    | (Control & Governance) |
+──────────────+                                  +────────────────────────+
      │                                                      ▲
      │ 3. Direct LLM Requests                               │ 4. Ingest Metrics
      │    (Keeps querying node until fail/429)              │    & Failures
      ▼                                                      │
+────────────────────────────────────────────────────────────┴─────────────+
|               Resource Nodes (LiteLLM Data Plane Proxies)                |
|           [Node gw-kr (Tailscale)]     [Node gw-us (Tailscale)]          |
+──────────────────────────────────────────────────────────────────────────+
```

### Request & Failover Lifecycle

1. **Discovery**: The `Application` (Consumer) initially queries the `litellm-control-plane` (e.g. `/health/summary` or `/nodes/available`) to find a healthy, active Resource Node.
2. **Resolution**: The Control Plane returns the address of an active node (e.g. `gw-kr`).
3. **Execution**: The Application queries the `Resource Node` directly for LLM chat completions. Per-request retries and failovers (e.g. between primary and backup keys on that node) are handled locally by LiteLLM.
4. **Monitoring**: The `Resource Node` continuously reports success/failure events back to the Control Plane.
5. **Re-routing**: If the active Resource Node fails entirely (or all quotas on it are depleted), the Application queries the Control Plane again to discover and switch to another active node (e.g. `gw-us`).

---

## Repository Structure

```text
litellm-control-plane/
├── README.md
├── pyproject.toml              # Python project configuration and dependencies
├── src/                        # Source code for the control plane
│   ├── api/                    # Control Plane REST API
│   ├── config/                 # Desired vs Applied configuration manager
│   ├── state/                  # Current runtime state tracking
│   ├── registry/               # Registries: node, provider, account, model, endpoint
│   ├── secrets/                # Doppler secret reference layer
│   ├── adapters/               # LiteLLM proxy API adapter
│   ├── policy/                 # Policy engine and routing profiles
│   ├── health/                 # Probe engine and account state machine
│   ├── rollout/                # Rollout orchestrator (canary, apply, rollback)
│   ├── events/                 # Callback/event ingestion
│   ├── metrics/                # Prometheus metrics & spend logging
│   └── audit/                  # Append-only state-change audit log
├── tests/                      # Testing suite
│   ├── unit/                   # Offline module unit tests
│   ├── integration/            # Multi-component flow validation
│   ├── provider_baseline/      # Upstream compatibility validation suite
│   └── failure_injection/      # Chaos & failover scenarios
├── examples/                   # Configuration & inventory examples
├── docs/                       # Specifications, ADRs, and runbooks
```

## Project Documentation Index

All core documentation, specifications, and recovery guides are stored in the [docs/](file:///h:/litellm-control-plane/docs/) directory. Below is a structured index of the available resources:

### 🚀 Core Setup & Operations
*   [**Getting Started Guide** (docs/getting-started.md)](file:///h:/litellm-control-plane/docs/getting-started.md): Walkthrough of Swagger API registration steps, model logical-to-physical parameter mappings, and end-to-end validation.
*   [**Deployment Guide** (docs/deployment-guide.md)](file:///h:/litellm-control-plane/docs/deployment-guide.md): Local installation instructions, virtual environment setups, Doppler injection, and containerized deployment notes.
*   [**FAQ** (docs/faq.md)](file:///h:/litellm-control-plane/docs/faq.md): Troubleshooting common configuration questions, stateless LiteLLM mode bypasses, and multi-node routing divisions.

### 📐 Architecture & Specifications
*   [**System Architecture** (docs/architecture.md)](file:///h:/litellm-control-plane/docs/architecture.md): Division of labor between Control Plane vs. LiteLLM Data Plane, networking topologies, and sync boundaries.
*   [**Data Model Specification** (docs/data-model.md)](file:///h:/litellm-control-plane/docs/data-model.md): Database schemas, relationships, and lifecycle states for Nodes, Accounts, Endpoints, and Consumers.
*   [**Policy & Routing Model** (docs/policy-model.md)](file:///h:/litellm-control-plane/docs/policy-model.md): Rules governing user access profiles, capability checks, and eligible endpoint candidates.
*   [**Rollout Model** (docs/rollout-model.md)](file:///h:/litellm-control-plane/docs/rollout-model.md): Detailed mechanics of Desired vs. Applied state synchronization, canaries, and dry runs.

### 🛡️ Security, Testing & Governance
*   [**Access Control Matrix** (docs/access-control-matrix.md)](file:///h:/litellm-control-plane/docs/access-control-matrix.md): Roles and endpoint permissions matrix.
*   [**Secrets Policy** (docs/secrets-policy.md)](file:///h:/litellm-control-plane/docs/secrets-policy.md): Standard practices for Doppler config layout, tokens, and key rotation.
*   [**AI Development Rules** (docs/ai-dev-rules.md)](file:///h:/litellm-control-plane/docs/ai-dev-rules.md): Coding guidelines, logging limits, and agent coding instructions.
*   [**Definition of Done** (docs/definition-of-done.md)](file:///h:/litellm-control-plane/docs/definition-of-done.md): Completion checklist for features, modules, and API integrations.
*   [**Testing Strategy** (docs/testing-strategy.md)](file:///h:/litellm-control-plane/docs/testing-strategy.md): Outlines unit tests, integration tests, and chaos failure injection.
*   [**Provider Baseline** (docs/provider-baseline.md)](file:///h:/litellm-control-plane/docs/provider-baseline.md): Test matrices to onboard new LLM providers before routing.

### 🚒 Operations Runbooks
Located in [docs/runbooks/](file:///h:/litellm-control-plane/docs/runbooks/):
*   [**Node Bootstrap** (docs/runbooks/node-bootstrap.md)](file:///h:/litellm-control-plane/docs/runbooks/node-bootstrap.md): Step-by-step setup to provision and register a new VPS proxy node.
*   [**Rollback Runbook** (docs/runbooks/rollback.md)](file:///h:/litellm-control-plane/docs/runbooks/rollback.md): Emergency recovery when a rollout fails or breaks routing.
*   [**Incident 429 Cooldown** (docs/runbooks/incident-429-cooldown.md)](file:///h:/litellm-control-plane/docs/runbooks/incident-429-cooldown.md): Diagnosing and mitigating provider rate limit limits.
*   [**LiteLLM Config Apply Failure** (docs/runbooks/litellm-config-apply-failure.md)](file:///h:/litellm-control-plane/docs/runbooks/litellm-config-apply-failure.md): Troubleshooting file-write or reload failures on remote nodes.
*   [**Doppler Token Expired** (docs/runbooks/doppler-token-expired.md)](file:///h:/litellm-control-plane/docs/runbooks/doppler-token-expired.md): How to replace revoked or expired Doppler config tokens.
*   [**Provider Key Rotation** (docs/runbooks/provider-key-rotation.md)](file:///h:/litellm-control-plane/docs/runbooks/provider-key-rotation.md): Procedure to cycle credentials without service interruption.
*   [**Tailscale Exit Node Failure** (docs/runbooks/tailscale-exit-node-failure.md)](file:///h:/litellm-control-plane/docs/runbooks/tailscale-exit-node-failure.md): Diagnostic steps for private VPN tunnel disconnects.

## Cross-Platform & Deployment Options

This codebase is designed to be highly portable and run identically on Windows, Linux, and macOS.

### Native Execution (Recommended for Dev & Local Testing)
Because the codebase is pure Python (>=3.12) and uses a serverless SQLite database, you can easily copy and run it anywhere natively. The database file (`control_plane.db`) is self-contained and fully binary-compatible across OS boundaries.

To run natively:
1. Initialize a virtual environment:
   ```bash
   python -m venv .venv
   ```
2. Install dependencies:
   * **Windows**: `.venv\Scripts\pip.exe install -r requirements.txt`
   * **Linux/macOS**: `.venv/bin/pip install -r requirements.txt`
3. Set the required admin key and start the API server:
   * **Windows** (PowerShell):
     ```powershell
     $env:CONTROL_PLANE_ADMIN_KEY="my-secret-key"
     .venv\Scripts\python.exe -m uvicorn src.api.main:app --reload
     ```
   * **Linux/macOS**:
     ```bash
     export CONTROL_PLANE_ADMIN_KEY="my-secret-key"
     .venv/bin/python -m uvicorn src.api.main:app --reload
     ```
   *(Note: The `control_plane.db` SQLite database is automatically created and initialized on startup).*

### Docker Containerization (Optional)
Using Docker is **completely optional** and not required for development or simple deployments. If containerized orchestration (such as Kubernetes) is desired:
1. Build the image:
   ```bash
   docker build -t litellm-control-plane .
   ```
2. Run the container (mounting a local host folder for SQLite persistence, and providing the admin key):
   ```bash
   docker run -p 8000:8000 -v ./data:/app/data -e CONTROL_PLANE_ADMIN_KEY="my-secret-key" litellm-control-plane
   ```

---

## LiteLLM Database & Virtual Keys
- **Recommended Setup**: To use the dynamic Virtual Key features of the control plane (such as automatically syncing keys for `Consumers`), the managed `LiteLLM` proxy nodes should be connected to a backend database (e.g. PostgreSQL, by setting the `DATABASE_URL` environment variable on the LiteLLM nodes).
- **Stateless/No-DB Bypass**: If your LiteLLM nodes are running in stateless mode without a database, the control plane's key-generation requests will fail, and synced keys will remain in `pending-sync` status. However, **you can still fully utilize model routing and failover**: simply use the node's static **Master Key** in the client's `Authorization` header to query the proxy, bypassing the virtual key requirement.

---

## Getting Started

Refer to the [deployment guide](file:///h:/litellm-control-plane/docs/deployment-guide.md) for local installation instructions.
For development details and AI coding constraints, see [ai-dev-rules.md](file:///h:/litellm-control-plane/docs/ai-dev-rules.md).

