# Runbook: Node Bootstrap

## Trigger Conditions
- Adding a new VM or container instance to act as a LiteLLM proxy within the `litellm-control-plane` topology.
- A previously failed node has been rebuilt and needs to be joined to the cluster.

## Diagnosis (Pre-flight Checks)
Before bootstrapping, ensure you have:
1. The static IP or hostname for the new node.
2. An assigned geographical or logical `region` (e.g., `us-east`, `eu-west`).
3. The designated `role` for the node (e.g., `proxy`, `exit`).

## Immediate Mitigation / Actions
1. **Provision the Node**: Set up a clean Linux VM or container.
2. **Install Dependencies**: Ensure Docker and Tailscale are installed.
3. **Join Tailnet**: 
   ```bash
   tailscale up --authkey <TAILSCALE_AUTH_KEY>
   ```
4. **Deploy LiteLLM Proxy**: Start the proxy process. (Ensure `LITELLM_MASTER_KEY` is set to a secure, newly generated string, and expose port 4000 to the Tailscale interface).
   ```bash
   docker run -d -p 4000:4000 -e LITELLM_MASTER_KEY="<MASTER_KEY>" ghcr.io/berriai/litellm:main-latest
   ```
5. **Register in Control Plane**:
   ```bash
   curl -X POST http://<control_plane_url>/registry/nodes \
        -H "Content-Type: application/json" \
        -d '{"id": "node-prod-03", "name": "Prod Proxy 3", "host": "100.x.y.z", "port": 4000, "region": "us-east", "role": "proxy"}'
   ```
6. **Assign Endpoints**: Link specific models and provider accounts to this new node via the `/registry/endpoints` API.

## Recovery Steps
1. Once registered and populated with Endpoints, the control plane knows the node exists but it does not yet have its configuration.
2. Trigger the initial configuration apply:
   ```bash
   curl -X POST http://<control_plane_url>/rollout/apply \
        -H "Content-Type: application/json" \
        -d '{"node_id": "node-prod-03"}'
   ```

## Validation After Recovery
1. Query the control plane node list to ensure the node shows as `status: active`.
2. Check the rollout timeline to verify `Rollout applied successfully` for the new node.
3. Use a test ConsumerKey mapped to this node and send a simple `GET /health/readiness` or a dummy `/v1/chat/completions` request.

## Escalation Notes
If the rollout fails during bootstrap, verify that the control plane can route to the node's Tailscale IP over the designated port. Ensure no firewalls are blocking the traffic.
