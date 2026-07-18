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

## Getting Started

Refer to the [deployment guide](file:///h:/litellm-control-plane/docs/deployment-guide.md) for local installation instructions.
For development details and AI coding constraints, see [ai-dev-rules.md](file:///h:/litellm-control-plane/docs/ai-dev-rules.md).
