# Runbook: Incident 429 Cooldown

## Trigger Conditions
- An automated alert triggers indicating high rate limiting (HTTP 429) across one or multiple endpoints.
- The incident timeline shows an Account transitioning to `cooldown`.

## Diagnosis
1. Check the incident timeline to identify the affected Account and the Provider.
   ```bash
   curl -X GET http://<control_plane_url>/timeline?limit=20
   ```
2. Verify if the 429s are isolated to a single Account (e.g., hitting tier limits) or if they affect the entire Provider (e.g., global OpenAI outage).
3. Check `litellm_active_incidents` metrics to see how many endpoints are currently degraded.

## Immediate Mitigation
Usually, the Health Manager handles this automatically by routing traffic to fallback endpoints. However, if the fallback logic is failing or if all accounts for a model group are saturated:
1. Temporarily disable the misbehaving account to prevent further request attempts:
   ```bash
   curl -X POST http://<control_plane_url>/events/override \
        -H "Content-Type: application/json" \
        -d '{"account_id": "<affected_account_id>", "action": "force-disabled"}'
   ```
2. Trigger a reconciliation rollout to immediately push the updated routing topology to all nodes:
   ```bash
   curl -X POST http://<control_plane_url>/rollout/reconcile \
        -H "Content-Type: application/json" \
        -d '{"node_id": "<affected_node_id>"}'
   ```

## Recovery Steps
1. Once the provider's rate limit window resets (usually 1-5 minutes, depending on the provider and tier), remove the manual override:
   ```bash
   curl -X POST http://<control_plane_url>/events/override \
        -H "Content-Type: application/json" \
        -d '{"account_id": "<affected_account_id>", "action": "none"}'
   ```
2. Wait for the Health Manager's probe engine to ping the account and automatically transition it from `cooldown` -> `recovered` -> `active`.

## Validation After Recovery
1. Monitor the timeline to verify the `recovered` and `active` transitions.
2. Confirm that traffic is being routed to the account again without 429 errors.

## Escalation Notes
If 429s persist across all accounts for a specific provider, the provider may be experiencing a global degradation. Escalate to the platform team and consider modifying the Policy Profiles to drop traffic for that provider entirely until resolved.
