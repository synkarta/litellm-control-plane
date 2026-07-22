import json
import logging
import sqlite3
from typing import List, Optional
from src.registry import store
from src.registry.models import Endpoint

logger = logging.getLogger("policy_engine")

def get_candidate_endpoints(
    conn: sqlite3.Connection,
    consumer_id: str,
    model_group: str
) -> List[Endpoint]:
    """
    Evaluate eligibility and return candidate endpoints matching the consumer's policy
    and the requested logical model group.
    """
    consumer = store.get_consumer(conn, consumer_id)
    if not consumer or consumer.status != "active":
        logger.debug(f"Consumer {consumer_id} not found or inactive.")
        return []

    # Default to least-privilege blocking if no profile is assigned
    if not consumer.profile_id:
        logger.debug(f"Consumer {consumer_id} has no policy profile assigned.")
        return []

    profile = store.get_policy_profile(conn, consumer.profile_id)
    if not profile:
        logger.debug(f"Policy profile {consumer.profile_id} for consumer {consumer_id} not found.")
        return []

    try:
        allowed_groups = json.loads(profile.allowed_model_groups)
    except Exception as e:
        logger.error(f"Failed to parse allowed_model_groups for profile {profile.id}: {e}")
        return []

    if model_group not in allowed_groups:
        logger.debug(f"Model group {model_group} not allowed by profile {profile.id} for consumer {consumer_id}.")
        return []

    # Retrieve all endpoints for the requested model group
    cursor = conn.execute(
        """
        SELECT 
            e.id, e.node_id, e.account_id, e.model_id, e.priority, e.weight, 
            e.status, e.manual_override, e.cooldown_until, e.failure_count
        FROM endpoints e
        JOIN models m ON e.model_id = m.id
        JOIN accounts a ON e.account_id = a.id
        WHERE m.logical_group = ?
        """,
        (model_group,)
    )
    endpoints = [Endpoint.model_validate(dict(row)) for row in cursor.fetchall()]

    candidates = []
    for e in endpoints:
        acc = store.get_account(conn, e.account_id)
        if not acc:
            continue

        acc_status = acc.status
        manual_override = e.manual_override
        ep_status = e.status

        # Exclusion checks (matching ConfigGenerator.generate_config logic)
        if manual_override == "force-disabled":
            continue

        if manual_override != "force-active":
            if ep_status in ("disabled", "cooldown", "degraded"):
                continue
            if acc_status in ("disabled", "inactive", "cooldown"):
                continue
        else:
            if acc_status in ("disabled", "inactive"):
                continue

        candidates.append(e)

    return candidates
