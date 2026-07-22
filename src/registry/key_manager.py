import logging
import os
import re
import sqlite3
from typing import List, Optional
from src.registry import store
from src.registry.models import ConsumerKeyCreate, ConsumerKey, Consumer
from src.adapters.litellm_adapter import LiteLLMAdapter

logger = logging.getLogger("key_manager")

# Placeholder prefix for keys that could not be provisioned on the node.
_PENDING_KEY_PREFIX = "pending-key-"

def get_node_master_key(node_id: str) -> str:
    """
    Resolve the master key for a LiteLLM proxy node.
    Checks env variable LITELLM_MASTER_KEY_<NODE_ID> (normalized),
    then LITELLM_MASTER_KEY, defaulting to 'sk-1234'.
    """
    norm = re.sub(r"[^A-Za-z0-9]", "_", node_id).upper()
    env_name = f"LITELLM_MASTER_KEY_{norm}"
    key = os.getenv(env_name) or os.getenv("LITELLM_MASTER_KEY")
    if key:
        return key
    raise RuntimeError(f"Missing master key for node '{node_id}'. Expected {env_name} or LITELLM_MASTER_KEY in environment.")

def get_node_url(node_host: str, node_port: int) -> str:
    """
    Format node host/port into a complete URL.

    Rules:
    - Strip trailing slashes from host.
    - If host already contains a port (after stripping scheme), do not append port.
    - If host doesn't start with a scheme, add http://.
    """
    host = node_host.rstrip("/")

    # Strip scheme for port-already-embedded check
    stripped = re.sub(r"^https?://", "", host)
    if ":" in stripped:
        # Port already embedded in host — return as-is
        if not host.startswith(("http://", "https://")):
            host = f"http://{host}"
        return host

    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    return f"{host}:{node_port}"

def get_consumer_models_scope(conn: sqlite3.Connection, consumer_id: str) -> List[str]:
    """
    Determine which logical model groups the consumer is allowed to access.
    Respects Policy Profiles assigned to the consumer.
    """
    import json
    consumer = store.get_consumer(conn, consumer_id)
    if not consumer or not consumer.profile_id:
        return []
    profile = store.get_policy_profile(conn, consumer.profile_id)
    if not profile:
        return []
    try:
        return json.loads(profile.allowed_model_groups)
    except Exception:
        return []

def sync_consumer_to_all_nodes(conn: sqlite3.Connection, consumer_id: str) -> None:
    """
    Synchronizes a consumer's virtual key across all active proxy/exit nodes.
    """
    consumer = store.get_consumer(conn, consumer_id)
    if not consumer:
        return

    # Fetch all active proxy/exit nodes
    nodes = store.list_nodes(conn)
    active_proxies = [n for n in nodes if n.status == "active" and n.role in ("proxy", "exit")]
    allowed_models = get_consumer_models_scope(conn, consumer_id)


    for node in active_proxies:
        master_key = get_node_master_key(node.id)
        url = get_node_url(node.host, node.port)
        adapter = LiteLLMAdapter(url, master_key)

        existing_key = store.get_consumer_key(conn, consumer_id, node.id)
        metadata = {
            "consumer_id": consumer.id,
            "name": consumer.name
        }

        if not existing_key:
            # Generate new key on node
            try:
                res = adapter.generate_key(
                    models=allowed_models,
                    metadata=metadata,
                    max_budget=consumer.max_budget,
                    rate_limit_rpm=consumer.rate_limit_rpm,
                    rate_limit_tpm=consumer.rate_limit_tpm
                )
                virtual_key = res["key"]
                key_status = "active"
            except Exception as e:
                logger.error(
                    f"Failed to generate key for {consumer_id} on node {node.id}: {e}"
                )
                virtual_key = f"{_PENDING_KEY_PREFIX}{node.id}-{consumer.id}"
                key_status = "pending-sync"

            store.create_consumer_key(
                conn,
                ConsumerKeyCreate(
                    consumer_id=consumer.id,
                    node_id=node.id,
                    virtual_key=virtual_key,
                    status=key_status
                ),
                actor="key-manager",
                reason="auto sync key creation"
            )

        elif existing_key.status == "pending-sync":
            # Try to recover: generate a real key to replace the placeholder
            try:
                res = adapter.generate_key(
                    models=allowed_models,
                    metadata=metadata,
                    max_budget=consumer.max_budget,
                    rate_limit_rpm=consumer.rate_limit_rpm,
                    rate_limit_tpm=consumer.rate_limit_tpm
                )
                # Route through audited store function (fixes H1)
                store.update_consumer_key(
                    conn,
                    consumer_id=consumer.id,
                    node_id=node.id,
                    virtual_key=res["key"],
                    status="active",
                    actor="key-manager",
                    reason="pending-sync recovery"
                )
            except Exception as e:
                logger.warning(
                    f"Recovery attempt failed for {consumer_id} on node {node.id}: {e}"
                )

        else:
            # Key is active; update limits on the node
            try:
                adapter.update_key(
                    key=existing_key.virtual_key,
                    models=allowed_models,
                    metadata=metadata,
                    max_budget=consumer.max_budget,
                    rate_limit_rpm=consumer.rate_limit_rpm,
                    rate_limit_tpm=consumer.rate_limit_tpm
                )
            except Exception as e:
                logger.warning(
                    f"Failed to update key for {consumer_id} on node {node.id}: {e}"
                )
                store.update_consumer_key_status(
                    conn, consumer.id, node.id, "pending-sync",
                    actor="key-manager", reason="sync failure on update"
                )

def delete_consumer_from_all_nodes(conn: sqlite3.Connection, consumer_id: str) -> None:
    """
    Revokes and deletes consumer keys across all nodes.
    For pending-sync placeholder keys, skips the remote revocation call.
    """
    keys = store.list_consumer_keys(conn, consumer_id=consumer_id)
    for key in keys:
        # M4 fix: only call the proxy if this is a real key (not a placeholder)
        is_placeholder = key.virtual_key.startswith(_PENDING_KEY_PREFIX) or key.status == "pending-sync"
        if not is_placeholder:
            node = store.get_node(conn, key.node_id)
            if node:
                master_key = get_node_master_key(node.id)
                url = get_node_url(node.host, node.port)
                adapter = LiteLLMAdapter(url, master_key)
                try:
                    adapter.delete_key(key.virtual_key)
                except Exception as e:
                    logger.warning(
                        f"Failed to revoke key {key.virtual_key} on node {key.node_id}: {e}"
                    )

        store.delete_consumer_key(
            conn, consumer_id, key.node_id,
            actor="key-manager", reason="auto revoke key deletion"
        )

def reconcile_all_keys(conn: sqlite3.Connection) -> None:
    """
    Retry sync for all keys marked as pending-sync.
    """
    cursor = conn.execute("SELECT DISTINCT consumer_id FROM consumer_keys WHERE status = 'pending-sync'")
    stale_consumers = [row["consumer_id"] for row in cursor.fetchall()]
    for cid in stale_consumers:
        sync_consumer_to_all_nodes(conn, cid)
