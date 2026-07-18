# ADR 0004: Node-Based Config Subsets

## Status
Accepted

## Context
In a multi-region deployment (e.g., VPS nodes in Korea, US, and China, plus local NAS and GPU nodes), not all nodes have access to the same resources or network exits. For instance:
*   A local GPU node (running Ollama) is only accessible locally or via a Tailscale IP.
*   China-based nodes may have network latency constraints preventing them from connecting to certain US-restricted endpoints directly without going through a designated egress exit node.
*   Certain accounts are geographically restricted due to compliance or terms of service (e.g. data residency in Europe).

If we generate a single global config file and push it to all LiteLLM proxies, every proxy will attempt to connect to all endpoints, violating compliance constraints and generating network errors.

## Decision
The control plane will generate **Node-Specific Config Subsets**:
1.  **Topology Mapping**: Every LiteLLM proxy node in our inventory will be classified by its tags (region, compliance zone, capability).
2.  **Eligible Endpoint Filtering**: During config generation, the Policy Engine will filter active endpoints for each node individually, based on node-level compliance and egress routes.
3.  **Scoped Config Delivery**: The Config Generator will produce unique config YAML files tailored for each node. A proxy node will only receive configuration definitions for endpoints it is allowed and able to reach.

## Consequences
*   **Safety**: Geographically restricted accounts or local-only models are isolated and never exposed to unauthorized nodes.
*   **Scale**: Individual config file sizes remain small and optimized for each node's local resources.
*   **Complexity**: The Rollout Orchestrator must manage multiple target configurations instead of pushing a single file globally. We must track the `applied_state` per node.

## Alternatives Considered
*   *Global Shared Config*: Having all nodes share one `config.yaml` containing all endpoints, and using LiteLLM routing rules to handle exclusions. Rejected because it exposes API keys (resolved from Doppler) of restricted endpoints to all nodes, violating least-privilege security principles.
