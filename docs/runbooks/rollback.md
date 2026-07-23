# Runbook: Rollback

## Trigger Conditions
- A recent deployment or configuration rollout via `/rollout/apply` has failed the canary test.
- The control plane's metrics show a sudden spike in `litellm_request_errors_total` immediately following a config change.
- A downstream client reports consistent 5xx errors affecting all models on a specific node.

## Diagnosis
1. Check the rollout timeline:
   ```bash
   curl -X GET http://<control_plane_url>/timeline?limit=10
   ```
   Look for `Rollout applied successfully` followed closely by 5xx incidents or endpoint degradation.
2. Confirm the currently applied config version on the node vs the desired config version.

## Immediate Mitigation
Trigger a manual rollback for the affected node to restore the previous known-good state.
```bash
curl -X POST http://<control_plane_url>/rollout/reconcile \
     -H "Content-Type: application/json" \
     -d '{"node_id": "<affected_node_id>", "force_rollback": true}'
```

## Recovery Steps
1. The orchestrator will parse the rollback target, generate the older config structure, and push it to the node.
2. The orchestrator will delete any orphaned virtual keys introduced by the bad rollout.
3. Wait 10 seconds for the node's LiteLLM process to hot-reload.

## Validation After Recovery
1. Query the node's proxy directly to ensure it is routing correctly.
2. Check the timeline to verify a `Rollout rolled_back` event is logged.
3. Monitor metrics to ensure `litellm_request_errors_total` drops back to baseline.

## Escalation Notes
If the rollback fails or the LiteLLM node refuses to accept the older configuration, SSH into the node and manually restart the LiteLLM process to force a clean initialization.
