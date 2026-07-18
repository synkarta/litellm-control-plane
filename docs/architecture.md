# Architecture Documentation

This document describes the overall system architecture, boundaries, and key design patterns of the `litellm-control-plane`.

## 1. System Boundary: Control Plane vs. Data Plane

The control plane sits *outside* the request path. It governs resources, configuration, health, policies, and secrets, while LiteLLM serves as the runtime gateway (the data plane) executing individual API requests.

```
       +-----------------------+
       |   API Clients / IDEs  |
       +-----------------------+
                   |
                   v (OpenAI API / Virtual Key)
+-------------------------------------------------+
|               LITELLM DATA PLANE                |
| - Virtual Key Verification & Spend tracking     |
| - Low-latency Request Routing & Load Balancing  |
| - Provider Protocol Translation (OpenAI -> Anthropic)
| - Fast-path Retries & per-request Failover      |
+-------------------------------------------------+
    ^                                        |
    | [1] Apply Config                       | [2] Callbacks & Spend Events
    |                                        v
+-------------------------------------------------+
|             LITELLM CONTROL PLANE               |
| - Inventory Registry (Nodes, Providers, Accounts)|
| - Policy Engine (Logical -> Candidate Endpoints)|
| - Doppler Secret Reference Mapping              |
| - Account State Machine & Cooldowns             |
| - Rollout Orchestrator (Canary & Rollback)       |
+-------------------------------------------------+
```

### Key Division of Labor
*   **LiteLLM (Data Plane)**: Must remain highly available and low latency. It does not perform database lookups, query policy matrices, or load secrets from Doppler. It operates entirely on the local config file and virtual-key database injected by the control plane.
*   **Control Plane**: Runs asynchronously from the request execution. It compiles the global inventory, filters it via active policies, maps Doppler secret references, generates valid LiteLLM config files, and rolls them out incrementally.

---

## 2. Sync vs. Async Paths in the Control Plane

To prevent blocking operations, the control plane is designed around a clear separation of synchronous and asynchronous processes:

### Synchronous Paths (REST APIs)
*   **Registry CRUD**: Operators adding, modifying, or removing nodes, providers, accounts, and policies in the SQLite/Postgres metadata store.
*   **Desired State Compiling**: Generating the target configuration snapshot without deploying it.
*   **Config Validation**: Validation of generated configurations against baseline schemas and secret presence before deployment.

### Asynchronous Paths (Background Workers)
*   **Callback/Event Ingestion**: Ingesting webhook success/failure events and spend data sent by LiteLLM instances. These events are processed out-of-band to update the Account State Machine.
*   **Active Probing**: The Probe Engine scheduling lightweight health checks to endpoints or accounts that are in a `probe` or `degraded` state.
*   **Rollout Orchestrator**: Coordinating multi-step canaries, monitoring target nodes for success/failure, and applying rollbacks if drift or elevated error rates are detected.

---

## 3. Resource Relationships and Entity Map

The control plane models infrastructure using a multi-layered hierarchy:

```
  [Node] (Location, Network Endpoint, Exit Routing)
    |
    +---> [Endpoint] (Concrete combination of Node + Account + Model)
            |
  [Account] (Credentials & Quotas, owned by Provider)
    |
  [Provider] (Vendor metadata: OpenAI, Anthropic, Ollama, NIM)
```

1.  **Node**: A logical execution unit (e.g., VPS in Korea, a local GPU server, an Ollama endpoint).
2.  **Provider**: An AI vendor definition (e.g., OpenAI, Anthropic, Azure, or Self-Hosted).
3.  **Account**: A specific billing or API account under a Provider (e.g., "Company-Anthropic-Prod-01").
4.  **Model Group**: A logical grouping of models (e.g., `gpt-4o`, `claude-3-5-sonnet`) mapped to consumer capabilities.
5.  **Endpoint**: A routable endpoint generated from the intersection of a `Node`, an `Account`, and a `Model`.

---

## 4. Integration with Doppler & Tailscale

### Doppler (Secrets Management)
*   The control plane **never** stores raw secret values (API keys, admin passwords) in its database.
*   The control plane stores **Secret References** (e.g., `doppler://PROJECT/CONFIG/SECRET_NAME`).
*   During config generation, the control plane uses config-scoped Doppler Service Tokens to resolve the credentials temporarily and injects them into the generated LiteLLM config.
*   A compromised inference node only receives the subset of secrets relevant to the accounts and endpoints assigned to it.

### Tailscale (Private Networking)
*   VPS nodes and local inference endpoints communicate over a secure Tailscale mesh.
*   Endpoints that require specific geo-location egress use Tailscale Exit Nodes.
*   Control plane configuration generators specify the correct egress paths and Tailscale proxy ports to route API calls safely.

---

## 5. Source of Truth

*   **Desired State**: The Control Plane database (SQLite in MVP, Postgres in Production) is the single source of truth for the system's intended configuration, policy bindings, and registries.
*   **Applied State**: The configurations currently active on individual LiteLLM nodes. The control plane periodically queries nodes to detect config drift and reconcile discrepancies.
*   **Runtime Secrets**: Doppler is the source of truth for raw credentials.
