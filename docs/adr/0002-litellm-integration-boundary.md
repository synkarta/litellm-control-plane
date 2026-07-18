# ADR 0002: LiteLLM Integration Boundary

## Status
Accepted

## Context
LiteLLM comes with native support for model groups, fallback pools, cooldown triggers, and virtual keys. We want to leverage these native features rather than building parallel systems. For example, if we create our own virtual-key verification database or request-path routing scheduler in the control plane, we will break compatibility with standard LiteLLM deployments and lose its optimized performance characteristics.

## Decision
We will interface with LiteLLM using its native concepts:
1.  **Model Configuration**: The control plane will generate LiteLLM-compatible `config.yaml` files containing standard `model_list` entries, rather than attempting to route requests directly.
2.  **Virtual Keys**: Instead of implementing a parallel access control model, consumer identities (`coding-agent`, `chatbot`) will be mapped directly to LiteLLM virtual keys, reusing LiteLLM's budget, rate-limiting, and allowed-model rules.
3.  **Callback Processing**: The control plane will ingest LiteLLM logging callbacks (success, failure, spend logs) to monitor account performance and detect failures, translating these logs into control-plane state changes.

## Consequences
*   **Decoupled Upstream Adapters**: We do not need to write or maintain custom providers for OpenAI, Anthropic, or Cohere; LiteLLM handles all API translation natively.
*   **Virtual Key Lifecycle**: We must implement a Virtual Key Manager module inside the control plane that calls the LiteLLM admin REST endpoints (`/key/generate`, `/key/update`) to sync keys.
*   **Latency**: Control plane operations (e.g., policy recalculations, key updates) are eventually consistent on the data plane, bounded by the speed of the config apply and sync workflows.

## Alternatives Considered
*   *Custom Routing Proxy*: Intercepting requests and choosing the endpoint before forwarding to LiteLLM. Rejected because LiteLLM already load-balances between endpoints within a model group. We should instead control *which* endpoints are placed in that model group in the generated config.
