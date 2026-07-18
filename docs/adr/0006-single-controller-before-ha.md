# ADR 0006: Single Controller before HA

## Status
Accepted

## Context
A control plane can be deployed in an Active-Active high-availability (HA) configuration, requiring raft-based database clustering (e.g. CockroachDB, dqlite) or distributed consensus locks (consul, etcd) to coordinate node configurations and prevent split-brain rollouts.
While HA improves control plane availability, it adds substantial engineering overhead, makes local development difficult, and increases cluster bootstrap complexity.

## Decision
For the MVP, we will design for a **Single Active Controller**:
1.  **Passive Standby Support**: The control plane backend will run as a single active process. If we deploy backups, they will run in a passive standby configuration (Active-Passive).
2.  **Shared Database**: SQLite will be used for local development and single-node MVP. Postgres will be supported for multi-host deployments, allowing standby controllers to point to the same database.
3.  **Graceful Recovery**: If the active controller crashes, the data plane (LiteLLM nodes) will continue running uninterrupted. The controller can recover its state upon restart by reading the persisted database and pulling active configurations from the LiteLLM nodes (Reconciliation).

## Consequences
*   **Simple Implementation**: No consensus protocols or distributed locks are needed in the MVP.
*   **Availability**: The control plane itself is a single point of failure for *modifications* (adding nodes, rotating keys, failover coordination), but **not** for request serving (which is isolated in LiteLLM).
*   **Recovery Objective**: The system accepts a recovery time objective (RTO) of several minutes (time to spin up a new container and run reconciliation) during control plane failures.

## Alternatives Considered
*   *Distributed dqlite Cluster*: Running clustered SQLite databases on all controller nodes. Rejected because it exceeds the complexity budget of an MVP.
