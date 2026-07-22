import sqlite3
from typing import Any, Dict, List, Optional
from src.registry import store

def get_health_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Aggregate health states of all nodes, accounts, and endpoints into a single summary payload.
    """
    nodes = store.list_nodes(conn)
    accounts = store.list_accounts(conn)
    endpoints = store.list_endpoints(conn)

    # Build endpoint index by node_id for aggregation
    endpoints_by_node: Dict[str, list] = {}
    for e in endpoints:
        endpoints_by_node.setdefault(e.node_id, []).append(e)

    # Structure nodes list with aggregated health
    node_summary = []
    for n in nodes:
        node_eps = endpoints_by_node.get(n.id, [])
        if not node_eps:
            # No endpoints: report node's own DB status
            agg_health = n.status
        else:
            statuses = {e.status for e in node_eps}
            if statuses == {"disabled"}:
                agg_health = "disabled"
            elif statuses <= {"active", "recovered"}:
                agg_health = "active"
            elif "cooldown" in statuses or "degraded" in statuses or "probe" in statuses:
                agg_health = "degraded"
            else:
                agg_health = n.status

        node_summary.append({
            "id": n.id,
            "name": n.name,
            "region": n.region,
            "role": n.role,
            "status": n.status,           # raw DB status
            "health": agg_health,         # aggregated from endpoints
            "endpoint_count": len(node_eps),
        })

    # Structure accounts list
    account_summary = []
    for a in accounts:
        account_summary.append({
            "id": a.id,
            "name": a.name,
            "provider_id": a.provider_id,
            "status": a.status,
            "cooldown_until": a.cooldown_until,
            "failure_count": a.failure_count
        })

    # Structure endpoints list
    endpoint_summary = []
    for e in endpoints:
        endpoint_summary.append({
            "id": e.id,
            "node_id": e.node_id,
            "account_id": e.account_id,
            "model_id": e.model_id,
            "status": e.status,
            "manual_override": e.manual_override,
            "cooldown_until": e.cooldown_until,
            "failure_count": e.failure_count
        })

    return {
        "nodes": node_summary,
        "accounts": account_summary,
        "endpoints": endpoint_summary
    }

def get_incidents_list(
    conn: sqlite3.Connection,
    limit: int = 100,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    state_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve list of active and historical health state transition events.
    Optional filters: target_type ('account'|'endpoint'), target_id, state_to.
    """
    return store.list_incidents(
        conn,
        limit=limit,
        target_type=target_type,
        target_id=target_id,
        state_to=state_to,
    )
