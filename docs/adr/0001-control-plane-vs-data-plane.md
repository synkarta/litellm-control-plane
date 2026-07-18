# ADR 0001: Control Plane vs. Data Plane Separation

## Status
Accepted

## Context
LiteLLM serves as a highly performant, OpenAI-compatible proxy that supports request routing, load balancing, virtual key management, and retries. However, managing multiple instances of LiteLLM in a multi-region, multi-account setup requires a central administrative node to coordinate physical registries, secret injection, account lifecycle states (degradations, cooldowns), and staged config rollouts.

If we build these governance tools directly into LiteLLM or create a second gateway that intercepts all incoming API requests, we would introduce extra latency, duplicate the request-path routing mechanics, and complicate high-availability deployments.

## Decision
We will establish a strict separation between the **Data Plane** and the **Control Plane**:
1.  **LiteLLM Data Plane**: Serves as the primary request path. It handles request-response lifecycle, streaming translation, token tracking, and immediate retries.
2.  **LiteLLM Control Plane**: Operates out-of-band. It compiles logical inventory, tracks account health states via callbacks, resolves secret references from Doppler, and generates and pushes configuration sets.
3.  **Interface Boundary**: The control plane interfaces with the data plane strictly via declarative configuration files, the LiteLLM Admin API, and asynchronous callback webhooks.

## Consequences
*   **Performance**: Zero additional latency is added to the user request path, as the control plane does not act as a middleman for API calls.
*   **Resilience**: If the control plane goes down, the LiteLLM proxies continue to serve requests normally using their last-known-good configuration.
*   **Complexity**: We must maintain config synchronization and drift detection, as the applied configuration on LiteLLM could drift from the control plane's desired state.

## Alternatives Considered
*   *In-Gateway Control Plane*: Modifying LiteLLM middleware to query a central database on every request. Rejected due to latency overhead and single-point-of-failure risks.
*   *Reverse Proxy Controller*: Placing a custom Nginx or custom proxy in front of LiteLLM. Rejected because LiteLLM already handles virtual keys and gateway routing; a second proxy is redundant.
