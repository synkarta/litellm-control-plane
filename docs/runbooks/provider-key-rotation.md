# Runbook: Provider Key Rotation

## Trigger Conditions
- Routine security policy requires rotating upstream provider API keys (e.g., OpenAI, Anthropic).
- A provider API key is suspected to be compromised.
- An account is consistently returning 401 Unauthorized errors in the incident timeline.

## Diagnosis
1. Check the incident timeline to confirm if the rotation is proactive or reactive (due to 401s).
2. Identify the `Account` IDs in the control plane that rely on the compromised/rotating key.

## Immediate Mitigation
1. If the key is compromised, immediately revoke the old key in the provider's official dashboard (e.g., OpenAI platform).
2. Generate a new key from the provider's dashboard.

## Recovery Steps
1. **Update Doppler**:
   Navigate to the Doppler project/config for the environment (e.g., `litellm-infra/prd_us`) and update the secret value (e.g., `OPENAI_API_KEY`) with the new key.
2. **Clear Control Plane Cache (Wait)**:
   The control plane's Doppler resolver caches secrets for 5 minutes (300 seconds). Wait 5 minutes, or restart the control plane process to clear the in-memory cache immediately.
3. **Reconcile Nodes**:
   The new secret is in Doppler, but the LiteLLM proxy nodes are still holding the old config in memory. Trigger a global reconciliation across all affected nodes:
   ```bash
   curl -X POST http://<control_plane_url>/rollout/reconcile \
        -H "Content-Type: application/json" \
        -d '{"node_id": "<affected_node_id>"}'
   ```
   *(Repeat for all nodes mapped to the affected account).*

## Validation After Recovery
1. The orchestrator will regenerate the config, fetch the fresh secret from Doppler, and apply it to the nodes.
2. Monitor the `litellm_request_errors_total` metrics to ensure 401 Unauthorized errors drop to zero.
3. Check the timeline to ensure the Account transitions from `degraded`/`cooldown` back to `recovered` and `active`.

## Escalation Notes
If 401 errors continue after the rollout, verify that the `secret_ref` in the Account object perfectly matches the Doppler project, config, and secret name that you just updated.
