# ADR 0005: No Plugin Runtime in MVP

## Status
Accepted

## Context
We want the policy engine of the control plane to be highly customizable, allowing routing decisions based on time of day, user identity, cost, and historical latency. One way to achieve this is by embedding a plugin runtime (such as WASM, Lua, or dynamic Python loading) to let operators write custom code to run during configuration updates.

However, implementing a sandboxed plugin runtime adds significant complexity, introduces potential security vulnerabilities, increases the risk of resource leaks, and makes it harder to guarantee deterministic config generation.

## Decision
For the MVP, we will **not support a custom plugin runtime**:
1.  **Declarative Policies**: Policies will be written as structured metadata configurations (JSON or YAML) matching a predefined domain model.
2.  **Core Heuristics**: Custom selection criteria (e.g. latency constraints, cost limits) will be implemented as compiled python code within the core `litellm-control-plane` package, controlled by configuration flags.
3.  **No Dynamic Code Loading**: No external code will be loaded or executed at runtime.

## Consequences
*   **Safety**: Simplified threat model; code execution is limited to the vetted control plane codebase.
*   **Determinism**: Policy decisions are fully deterministic and explainable from the input database state and YAML policies alone.
*   **Flexibility**: Operators cannot write arbitrary script hooks. If a new policy rule is needed, it must be developed as a code change to the policy engine and rolled out through standard deployment pipelines.

## Alternatives Considered
*   *Embedded WASM Runtime*: Running WebAssembly binaries for custom policy hooks. Rejected due to MVP timeline constraints.
*   *Dynamic Python Module Loading*: Loading arbitrary python files from a designated directory. Rejected due to the risk of code injection and runtime instability.
