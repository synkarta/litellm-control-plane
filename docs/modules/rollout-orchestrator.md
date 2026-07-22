# Rollout Orchestrator

The Rollout Orchestrator manages the lifecycle of node configurations: compiling, deploying, validating, and rolling back configs.

## Responsibilities
- Compile node topology into LiteLLM-compatible configurations.
- Deploy generated configs safely to node config files.
- Verify node readiness after deployment by polling the `/health/readiness` endpoint.
- Automate rollbacks to the last successful config in case of verification failures or timeouts.
- Perform drift detection between disk configurations and desired database states.

## Workflows
- **Rollout**: `deploy_config(conn, node_id, config_filepath)`
  - Generates config via `ConfigGenerator`.
  - Writes config to `config_filepath`.
  - Polls node health readiness.
  - Reverts to last successful config on failure.
- **Drift Check**: `detect_drift(conn, node_id, config_filepath)`
  - Compares file contents on disk with generated config structure.
  - Identifies missing or orphaned consumer keys.

## Invariants
- A failed rollout must never leave the proxy in an unhealthy state; it must always rollback.
- Rollbacks must be logged as independent audit events.
