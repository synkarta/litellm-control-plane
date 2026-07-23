# Runbook: LiteLLM Config Apply Failure

## Trigger Conditions
- An automated rollout via `/rollout/apply` or `/rollout/reconcile` transitions to the `failed` state.
- The control plane's orchestrator logs an exception when trying to communicate with a LiteLLM node during deployment.

## Diagnosis
1. Check the rollout timeline to identify the exact error message associated with the failure:
   ```bash
   curl -X GET http://<control_plane_url>/timeline?limit=10
   ```
2. Identify the failure stage:
   - **Generation Failure**: The Config Generator failed (e.g., could not resolve a secret, invalid SQLite state).
   - **Canary/Validation Failure**: The generated YAML is invalid, or the LiteLLM node rejected it.
   - **Deployment Failure**: Network timeout or SSH/Tailscale failure when pushing the config to the remote node.

## Immediate Mitigation
The orchestrator automatically aborts and marks the rollout as `failed`. No immediate manual action is required to prevent an outage, because the LiteLLM proxy continues running its last known good configuration.

## Recovery Steps
1. **If Generation Failure**: Fix the missing secret in Doppler or correct the invalid state in the registry, then re-trigger the rollout:
   ```bash
   curl -X POST http://<control_plane_url>/rollout/apply \
        -H "Content-Type: application/json" \
        -d '{"node_id": "<affected_node_id>"}'
   ```
2. **If Canary Failure**: Inspect the generated YAML (available in the Rollout object in the database) to find the syntax or structural error. Escalate to engineering to fix the `ConfigGenerator` logic.
3. **If Deployment Failure**: Verify network connectivity to the target node (e.g., check Tailscale status on the node). Once network is restored, run a reconciliation:
   ```bash
   curl -X POST http://<control_plane_url>/rollout/reconcile \
        -H "Content-Type: application/json" \
        -d '{"node_id": "<affected_node_id>"}'
   ```

## Validation After Recovery
1. Query the `/rollout/apply` endpoint and ensure the status returns `success`.
2. Check the timeline to confirm the successful configuration apply.

## Escalation Notes
If a config apply failure leaves a node in an inconsistent state (e.g., the YAML file was written but the LiteLLM process crashed during hot-reload), SSH into the node, manually restore the backup config (`config.yaml.bak`), and restart the service.
