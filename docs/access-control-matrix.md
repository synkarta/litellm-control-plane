# Access Control Matrix

This document defines the roles, permissions, and security boundaries within the `litellm-control-plane`. 

As the control plane handles highly sensitive operations (distributing credentials to proxies and defining cost/routing budgets), strict RBAC (Role-Based Access Control) principles apply.

## Roles

| Role Name | Description |
|-----------|-------------|
| **Operator (Write)** | Human administrators or high-privilege CI/CD runners managing the inventory and policy topology. |
| **Operator (Read)** | Analysts or monitoring systems needing visibility into incidents, drift, and current state. |
| **Automation** | Reconcilers or background task runners needing to trigger rollouts or adjust health states dynamically. |
| **Runtime Service** | The LiteLLM proxy itself (via the adapter) fetching configurations or validating virtual keys. |
| **Consumer (Internal API)** | Chatbots, agents, and downstream services consuming the LiteLLM proxy. |

## Permission Matrix

| Endpoint/Action | Operator (Write) | Operator (Read) | Automation | Runtime Service | Consumer |
|-----------------|------------------|-----------------|------------|-----------------|----------|
| `/registry/*` (GET) | ✅ Allow | ✅ Allow | ✅ Allow | ❌ Deny | ❌ Deny |
| `/registry/*` (POST, PATCH, DELETE) | ✅ Allow | ❌ Deny | ❌ Deny | ❌ Deny | ❌ Deny |
| `/events/override` (Manual Health Override) | ✅ Allow | ❌ Deny | ❌ Deny | ❌ Deny | ❌ Deny |
| `/events/callback` (Ingest LiteLLM signals) | ✅ Allow | ❌ Deny | ✅ Allow | ✅ Allow | ❌ Deny |
| `/rollout/*` (Apply & Reconcile) | ✅ Allow | ❌ Deny | ✅ Allow | ❌ Deny | ❌ Deny |
| Resolve Doppler Secrets | ✅ Allow | ❌ Deny | ✅ Allow | ❌ Deny | ❌ Deny |
| Proxy Data Path (e.g. `/v1/chat/completions`) | ❌ Deny (Handled by LiteLLM) | ❌ Deny | ❌ Deny | N/A | ✅ Allow (Using Virtual Keys) |

## Implementation Notes

- Currently, MVP APIs utilize the `X-Actor` header to track the actor in the Audit logs.
- Future milestones will enforce these permissions strictly via token-based middleware (JWT verification). 
- Access to raw secrets (Doppler tokens) is restricted strictly to the environment running the `Operator (Write)` tasks or `Automation` tasks. Downstream consumers NEVER see or touch these tokens.
