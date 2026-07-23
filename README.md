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

## System Architecture

The control plane sits above the LiteLLM proxy data plane:

```
+---------------------------------------+
|             Applications              | (Coding agents, Chat services, IDEs)
+---------------------------------------+
                   |
                   v (Requests / Virtual Keys)
+---------------------------------------+
|       LiteLLM Data Plane (Proxy)      | (Execution, translation, retries)
+---------------------------------------+
         ^                      ^
         | (Apply Config)       | (Metrics / Callbacks)
+---------------------------------------+
|        litellm-control-plane          | (Inventory, health state, policy)
+---------------------------------------+
         | (Scoping / Metadata)
         v
+---------------------------------------+
|  Infra Resources (Doppler, Tailscale) |
+---------------------------------------+
```

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
└── docs/                       # Specifications, ADRs, and runbooks
```

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

