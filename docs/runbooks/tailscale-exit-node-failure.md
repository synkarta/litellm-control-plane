# Runbook: Tailscale Exit Node Failure

## Trigger Conditions
- LiteLLM proxy nodes are completely failing to reach external upstream APIs (e.g., OpenAI, Anthropic), resulting in 100% 5xx or `httpx.ConnectTimeout` errors in the logs.
- The control plane Health Manager detects that *all* endpoints on a specific node (or all nodes in a region) have abruptly transitioned to `degraded` or `cooldown`.
- The node uses Tailscale to route egress traffic through a designated exit node, and that exit node has gone offline.

## Diagnosis
1. Verify the scope of the outage. Is it one proxy node, or all of them? 
2. SSH into one of the affected LiteLLM proxy nodes.
3. Test direct outbound internet connectivity:
   ```bash
   curl -I https://api.openai.com
   ```
   If it hangs or fails, the egress path is broken.
4. Check the Tailscale status on the proxy node:
   ```bash
   tailscale status
   ```
   Look for the status of the designated exit node. If it says `offline` or `active; relay "..."`, the direct connection to the exit node is dead or severely degraded.

## Immediate Mitigation
Bypass the failed exit node to restore service immediately.

1. On the affected LiteLLM proxy node(s), drop the exit node requirement:
   ```bash
   tailscale up --reset
   ```
   *(This restores standard outbound routing through the node's local network gateway, bypassing the Tailnet exit).*
2. Verify connectivity is restored:
   ```bash
   curl -I https://api.openai.com
   ```

## Recovery Steps
1. The control plane's Health Manager will automatically detect that the upstreams are reachable again.
2. Endpoints will transition from `cooldown` to `recovered`, and then `active`.
3. Check the incident timeline to confirm recovery.

## Restoring the Exit Node
Once the Tailscale exit node is fixed (rebooted, re-authenticated, or replaced):
1. On the proxy node(s), re-enable the exit node routing:
   ```bash
   tailscale up --exit-node=<exit_node_ip>
   ```
2. Verify connectivity again.

## Escalation Notes
If dropping the exit node does not restore connectivity, the problem is not Tailscale-related but likely a local ISP/VPC gateway failure or a global provider outage.
