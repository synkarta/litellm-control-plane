# Runbook: Doppler Token Expired or Invalid

## Trigger Conditions
- During a rollout apply or reconcile operation, the orchestrator logs a 401 Unauthorized or secret resolution failure specifically traced to the Doppler Service Token.
- Rollouts consistently transition to the `failed` state due to `ValueError("Unauthorized: Invalid Doppler Service Token")`.
- The `doppler_resolver` logs emit warnings that they are constantly falling back to local environment variables because token fetches are failing.

## Diagnosis
1. Check the control plane operational logs (e.g., systemd journal or docker logs) for the `doppler_resolver` logger output.
2. Identify which specific token is failing (the logs will mention the `project` and `config` it was trying to fetch).

## Immediate Mitigation
Because the control plane generator skips endpoints if it cannot resolve their secrets, a failed Doppler token will cause those endpoints to be dropped from the generated config. However, the orchestrator handles generation failures safely, meaning the **currently running LiteLLM nodes are unaffected** (they keep their old, valid config loaded in memory).

*Do not forcefully restart the LiteLLM proxy nodes during this incident! They will lose their in-memory secrets and go down completely.*

## Recovery Steps
1. **Rotate Service Token in Doppler**:
   Log into the Doppler dashboard, navigate to the affected Project -> Config, and revoke the expired service token.
   Generate a new service token for that environment.
2. **Inject New Token into Control Plane**:
   Update the deployment environment for the `litellm-control-plane` (e.g., Kubernetes Secret, systemd EnvironmentFile, or `.env` file).
   - Variable name: `DOPPLER_TOKEN_<PROJECT>_<CONFIG>` (e.g., `DOPPLER_TOKEN_LITELLM_INFRA_PRD_US`).
3. **Restart Control Plane**:
   Restart the control plane process so it picks up the new environment variable.
   ```bash
   systemctl restart litellm-control-plane
   # or docker restart ...
   ```
4. **Trigger Reconciliation**:
   Once the control plane is back up, verify that it can now fetch secrets by running a reconciliation on one node:
   ```bash
   curl -X POST http://<control_plane_url>/rollout/reconcile \
        -H "Content-Type: application/json" \
        -d '{"node_id": "<affected_node_id>"}'
   ```

## Validation After Recovery
1. The reconciliation API should return `success`.
2. Check the logs to ensure the `doppler_resolver` is no longer emitting fallback warnings.
3. Verify that the generated config (visible in the Rollout object) contains the correct number of endpoints.
