# Rollout and Deployment Model

This document outlines the deployment lifecycle, state transitions, and verification mechanics for LiteLLM configurations.

## State Transitions during Rollout

```mermaid
state_diagram
    [*] --> pending
    pending --> applying : write new config file
    applying --> success : health check verification passes
    applying --> failed : health check verification fails / timeout
    failed --> rolled_back : automatic restore of last success config
    rolled_back --> [*]
    success --> [*]
```

### Rollout Lifecycle

1. **Compilation**: Retrieve all endpoints configured for a node, resolve secrets (Doppler Resolver), format to YAML.
2. **Validation**: Check YAML schema & validity.
3. **Application**: Record state as `applying` and write YAML to node's config file.
4. **Verification**: Poll node `/health/readiness` for `timeout_sec` (default 10s).
   - If success: Update rollout to `success`.
   - If fail/timeout: Revert config file on disk to the last `success` configuration from database rollouts history. Write a new rollout record with status `rolled_back`. Raise error to block API.

### Drift Detection

Drift check detects configuration anomalies across two dimensions:
- **Config Drift**: Compares disk YAML file content against the desired state computed by `ConfigGenerator`.
- **Key Drift**: Scans database active consumers and flags any consumer key on the node that is either `missing` (consumer active but key missing) or `orphaned` (key present but consumer inactive/deleted).
