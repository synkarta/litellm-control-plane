import json
import sqlite3
from typing import Any, Dict, List, Optional
from src.audit.logger import log_audit
from src.registry.models import (
    Node, NodeCreate, NodeUpdate,
    Provider, ProviderCreate, ProviderUpdate,
    Model, ModelCreate, ModelUpdate,
    Account, AccountCreate,
    Endpoint, EndpointCreate,
    Consumer, ConsumerCreate, ConsumerUpdate,
    ConsumerKey, ConsumerKeyCreate,
    PolicyProfile, PolicyProfileCreate, PolicyProfileUpdate,
    Rollout
)

# --- Nodes Store ---

def create_node(conn: sqlite3.Connection, node: NodeCreate, actor: str, reason: Optional[str] = None) -> Node:
    try:
        conn.execute(
            """
            INSERT INTO nodes (id, name, host, port, region, role, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (node.id, node.name, node.host, node.port, node.region, node.role, node.status)
        )
        created = get_node(conn, node.id)
        assert created is not None
        log_audit(conn, actor, "create", "node", node.id, created.model_dump(), reason)
        return created
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Node already exists or database constraint failed: {e}")

def get_node(conn: sqlite3.Connection, node_id: str) -> Optional[Node]:
    row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if row:
        return Node.model_validate(dict(row))
    return None

def list_nodes(conn: sqlite3.Connection) -> List[Node]:
    cursor = conn.execute("SELECT * FROM nodes")
    return [Node.model_validate(dict(row)) for row in cursor.fetchall()]

def delete_node(conn: sqlite3.Connection, node_id: str, actor: str, reason: Optional[str] = None) -> bool:
    node = get_node(conn, node_id)
    if not node:
        return False
    
    conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
    log_audit(conn, actor, "delete", "node", node_id, node.model_dump(), reason)
    return True

def update_node(
    conn: sqlite3.Connection,
    node_id: str,
    update: NodeUpdate,
    actor: str,
    reason: Optional[str] = None
) -> Optional[Node]:
    old = get_node(conn, node_id)
    if not old:
        return None
    fields = update.model_dump(exclude_none=True)
    if not fields:
        return old
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [node_id]
    conn.execute(f"UPDATE nodes SET {set_clause} WHERE id = ?", values)
    new = get_node(conn, node_id)
    assert new is not None
    log_audit(conn, actor, "update", "node", node_id, {"before": old.model_dump(), "after": new.model_dump()}, reason)
    return new


# --- Providers Store ---

def create_provider(conn: sqlite3.Connection, provider: ProviderCreate, actor: str, reason: Optional[str] = None) -> Provider:
    try:
        conn.execute(
            """
            INSERT INTO providers (id, name, type)
            VALUES (?, ?, ?)
            """,
            (provider.id, provider.name, provider.type)
        )
        created = get_provider(conn, provider.id)
        assert created is not None
        log_audit(conn, actor, "create", "provider", provider.id, created.model_dump(), reason)
        return created
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Provider already exists or database constraint failed: {e}")

def get_provider(conn: sqlite3.Connection, provider_id: str) -> Optional[Provider]:
    row = conn.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
    if row:
        return Provider.model_validate(dict(row))
    return None

def list_providers(conn: sqlite3.Connection) -> List[Provider]:
    cursor = conn.execute("SELECT * FROM providers")
    return [Provider.model_validate(dict(row)) for row in cursor.fetchall()]

def delete_provider(conn: sqlite3.Connection, provider_id: str, actor: str, reason: Optional[str] = None) -> bool:
    provider = get_provider(conn, provider_id)
    if not provider:
        return False
    try:
        conn.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
        log_audit(conn, actor, "delete", "provider", provider_id, provider.model_dump(), reason)
        return True
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Cannot delete provider; it may be referenced by active accounts: {e}")

def update_provider(
    conn: sqlite3.Connection,
    provider_id: str,
    update: ProviderUpdate,
    actor: str,
    reason: Optional[str] = None
) -> Optional[Provider]:
    old = get_provider(conn, provider_id)
    if not old:
        return None
    fields = update.model_dump(exclude_none=True)
    if not fields:
        return old
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [provider_id]
    conn.execute(f"UPDATE providers SET {set_clause} WHERE id = ?", values)
    new = get_provider(conn, provider_id)
    assert new is not None
    log_audit(conn, actor, "update", "provider", provider_id, {"before": old.model_dump(), "after": new.model_dump()}, reason)
    return new


# --- Models Store ---

def create_model(conn: sqlite3.Connection, model: ModelCreate, actor: str, reason: Optional[str] = None) -> Model:
    try:
        conn.execute(
            """
            INSERT INTO models (id, name, logical_group, capability_chat, capability_stream, capability_tools, capability_embeddings)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model.id,
                model.name,
                model.logical_group,
                int(model.capability_chat),
                int(model.capability_stream),
                int(model.capability_tools),
                int(model.capability_embeddings)
            )
        )
        created = get_model(conn, model.id)
        assert created is not None
        log_audit(conn, actor, "create", "model", model.id, created.model_dump(), reason)
        return created
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Model already exists or database constraint failed: {e}")

def get_model(conn: sqlite3.Connection, model_id: str) -> Optional[Model]:
    row = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,)).fetchone()
    if row:
        d = dict(row)
        d["capability_chat"] = bool(d["capability_chat"])
        d["capability_stream"] = bool(d["capability_stream"])
        d["capability_tools"] = bool(d["capability_tools"])
        d["capability_embeddings"] = bool(d["capability_embeddings"])
        return Model.model_validate(d)
    return None

def list_models(conn: sqlite3.Connection) -> List[Model]:
    cursor = conn.execute("SELECT * FROM models")
    result = []
    for row in cursor.fetchall():
        d = dict(row)
        d["capability_chat"] = bool(d["capability_chat"])
        d["capability_stream"] = bool(d["capability_stream"])
        d["capability_tools"] = bool(d["capability_tools"])
        d["capability_embeddings"] = bool(d["capability_embeddings"])
        result.append(Model.model_validate(d))
    return result

def delete_model(conn: sqlite3.Connection, model_id: str, actor: str, reason: Optional[str] = None) -> bool:
    model = get_model(conn, model_id)
    if not model:
        return False
    try:
        conn.execute("DELETE FROM models WHERE id = ?", (model_id,))
        log_audit(conn, actor, "delete", "model", model_id, model.model_dump(), reason)
        return True
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Cannot delete model; it may be referenced by active endpoints: {e}")

def update_model(
    conn: sqlite3.Connection,
    model_id: str,
    update: ModelUpdate,
    actor: str,
    reason: Optional[str] = None
) -> Optional[Model]:
    old = get_model(conn, model_id)
    if not old:
        return None
    fields = update.model_dump(exclude_none=True)
    if not fields:
        return old
    # SQLite stores booleans as integers
    for bool_field in ("capability_chat", "capability_stream", "capability_tools", "capability_embeddings"):
        if bool_field in fields:
            fields[bool_field] = int(fields[bool_field])
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [model_id]
    conn.execute(f"UPDATE models SET {set_clause} WHERE id = ?", values)
    new = get_model(conn, model_id)
    assert new is not None
    log_audit(conn, actor, "update", "model", model_id, {"before": old.model_dump(), "after": new.model_dump()}, reason)
    return new


# --- Accounts Store ---

def create_account(conn: sqlite3.Connection, account: AccountCreate, actor: str, reason: Optional[str] = None) -> Account:
    try:
        conn.execute(
            """
            INSERT INTO accounts (id, name, provider_id, secret_ref, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (account.id, account.name, account.provider_id, account.secret_ref, account.status)
        )
        created = get_account(conn, account.id)
        assert created is not None
        log_audit(conn, actor, "create", "account", account.id, created.model_dump(), reason)
        return created
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Account constraints violated. Make sure provider_id exists: {e}")

def get_account(conn: sqlite3.Connection, account_id: str) -> Optional[Account]:
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if row:
        return Account.model_validate(dict(row))
    return None

def list_accounts(conn: sqlite3.Connection) -> List[Account]:
    cursor = conn.execute("SELECT * FROM accounts")
    return [Account.model_validate(dict(row)) for row in cursor.fetchall()]

def update_account_status(
    conn: sqlite3.Connection,
    account_id: str,
    status: str,
    actor: str,
    reason: Optional[str] = None
) -> Optional[Account]:
    old = get_account(conn, account_id)
    if not old:
        return None
    
    before_dict = old.model_dump()
    after_dict = {**before_dict, "status": status}
    
    if status == "active":
        conn.execute("UPDATE accounts SET status = ?, cooldown_until = NULL, failure_count = 0 WHERE id = ?", (status, account_id))
        after_dict["cooldown_until"] = None
        after_dict["failure_count"] = 0
    else:
        conn.execute("UPDATE accounts SET status = ? WHERE id = ?", (status, account_id))

    diff = {"before": before_dict, "after": after_dict}
    log_audit(conn, actor, "update_status", "account", account_id, diff, reason)
    return get_account(conn, account_id)

def delete_account(conn: sqlite3.Connection, account_id: str, actor: str, reason: Optional[str] = None) -> bool:
    account = get_account(conn, account_id)
    if not account:
        return False
    try:
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        log_audit(conn, actor, "delete", "account", account_id, account.model_dump(), reason)
        return True
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Cannot delete account; it may be referenced by active endpoints: {e}")


# --- Endpoints Store ---

def create_endpoint(conn: sqlite3.Connection, endpoint: EndpointCreate, actor: str, reason: Optional[str] = None) -> Endpoint:
    try:
        conn.execute(
            """
            INSERT INTO endpoints (id, node_id, account_id, model_id, priority, weight, status, manual_override)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                endpoint.id,
                endpoint.node_id,
                endpoint.account_id,
                endpoint.model_id,
                endpoint.priority,
                endpoint.weight,
                endpoint.status,
                endpoint.manual_override
            )
        )
        created = get_endpoint(conn, endpoint.id)
        assert created is not None
        log_audit(conn, actor, "create", "endpoint", endpoint.id, created.model_dump(), reason)
        return created
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Endpoint constraints violated. Make sure node_id, account_id, and model_id exist: {e}")

def get_endpoint(conn: sqlite3.Connection, endpoint_id: str) -> Optional[Endpoint]:
    row = conn.execute("SELECT * FROM endpoints WHERE id = ?", (endpoint_id,)).fetchone()
    if row:
        return Endpoint.model_validate(dict(row))
    return None

def list_endpoints(conn: sqlite3.Connection) -> List[Endpoint]:
    cursor = conn.execute("SELECT * FROM endpoints")
    return [Endpoint.model_validate(dict(row)) for row in cursor.fetchall()]

def update_endpoint_routing(
    conn: sqlite3.Connection,
    endpoint_id: str,
    priority: Optional[int],
    weight: Optional[int],
    actor: str,
    reason: Optional[str] = None
) -> Optional[Endpoint]:
    old = get_endpoint(conn, endpoint_id)
    if not old:
        return None
    
    new_priority = priority if priority is not None else old.priority
    new_weight = weight if weight is not None else old.weight
    
    conn.execute(
        "UPDATE endpoints SET priority = ?, weight = ? WHERE id = ?",
        (new_priority, new_weight, endpoint_id)
    )
    new = get_endpoint(conn, endpoint_id)
    assert new is not None
    diff = {"before": old.model_dump(), "after": new.model_dump()}
    log_audit(conn, actor, "update_routing", "endpoint", endpoint_id, diff, reason)
    return new

def update_endpoint_status(
    conn: sqlite3.Connection,
    endpoint_id: str,
    status: Optional[str],
    manual_override: Optional[str],
    actor: str,
    reason: Optional[str] = None
) -> Optional[Endpoint]:
    old = get_endpoint(conn, endpoint_id)
    if not old:
        return None
    
    new_status = status if status is not None else old.status
    new_override = manual_override if manual_override is not None else old.manual_override
    
    before_dict = old.model_dump()
    after_dict = {**before_dict, "status": new_status, "manual_override": new_override}
    
    if new_status == "active":
        conn.execute(
            "UPDATE endpoints SET status = ?, manual_override = ?, cooldown_until = NULL, failure_count = 0 WHERE id = ?",
            (new_status, new_override, endpoint_id)
        )
        after_dict["cooldown_until"] = None
        after_dict["failure_count"] = 0
    else:
        conn.execute(
            "UPDATE endpoints SET status = ?, manual_override = ? WHERE id = ?",
            (new_status, new_override, endpoint_id)
        )

    diff = {"before": before_dict, "after": after_dict}
    log_audit(conn, actor, "update_status", "endpoint", endpoint_id, diff, reason)
    return get_endpoint(conn, endpoint_id)

def delete_endpoint(conn: sqlite3.Connection, endpoint_id: str, actor: str, reason: Optional[str] = None) -> bool:
    endpoint = get_endpoint(conn, endpoint_id)
    if not endpoint:
        return False
    conn.execute("DELETE FROM endpoints WHERE id = ?", (endpoint_id,))
    log_audit(conn, actor, "delete", "endpoint", endpoint_id, endpoint.model_dump(), reason)
    return True


# --- Audit Logs Store ---

def list_audit_logs(conn: sqlite3.Connection, limit: int = 100) -> List[Dict[str, Any]]:
    cursor = conn.execute(
        "SELECT id, timestamp, actor, action, target_type, target_id, changes, reason FROM audit_logs ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    logs = []
    for row in cursor.fetchall():
        d = dict(row)
        try:
            d["changes"] = json.loads(d["changes"])
        except Exception:
            pass
        logs.append(d)
    return logs


# --- Consumers Store ---

def create_consumer(conn: sqlite3.Connection, consumer: ConsumerCreate, actor: str, reason: Optional[str] = None) -> Consumer:
    try:
        conn.execute(
            """
            INSERT INTO consumers (id, name, max_budget, rate_limit_rpm, rate_limit_tpm, status, profile_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                consumer.id,
                consumer.name,
                consumer.max_budget,
                consumer.rate_limit_rpm,
                consumer.rate_limit_tpm,
                consumer.status,
                consumer.profile_id
            )
        )
        created = get_consumer(conn, consumer.id)
        assert created is not None
        log_audit(conn, actor, "create", "consumer", consumer.id, created.model_dump(), reason)
        return created
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Consumer already exists or constraint failed: {e}")

def get_consumer(conn: sqlite3.Connection, consumer_id: str) -> Optional[Consumer]:
    row = conn.execute("SELECT * FROM consumers WHERE id = ?", (consumer_id,)).fetchone()
    if row:
        return Consumer.model_validate(dict(row))
    return None

def list_consumers(conn: sqlite3.Connection) -> List[Consumer]:
    cursor = conn.execute("SELECT * FROM consumers")
    return [Consumer.model_validate(dict(row)) for row in cursor.fetchall()]

def update_consumer(
    conn: sqlite3.Connection,
    consumer_id: str,
    update: ConsumerUpdate,
    actor: str,
    reason: Optional[str] = None
) -> Optional[Consumer]:
    old = get_consumer(conn, consumer_id)
    if not old:
        return None
    fields = update.model_dump(exclude_none=True)
    if not fields:
        return old
    
    before_dict = old.model_dump()
    after_dict = {**before_dict, **fields}

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [consumer_id]
    conn.execute(f"UPDATE consumers SET {set_clause} WHERE id = ?", values)
    
    diff = {"before": before_dict, "after": after_dict}
    log_audit(conn, actor, "update", "consumer", consumer_id, diff, reason)
    return get_consumer(conn, consumer_id)

def delete_consumer(conn: sqlite3.Connection, consumer_id: str, actor: str, reason: Optional[str] = None) -> bool:
    consumer = get_consumer(conn, consumer_id)
    if not consumer:
        return False
    conn.execute("DELETE FROM consumers WHERE id = ?", (consumer_id,))
    log_audit(conn, actor, "delete", "consumer", consumer_id, consumer.model_dump(), reason)
    return True


# --- Consumer Keys Store ---

def create_consumer_key(conn: sqlite3.Connection, consumer_key: ConsumerKeyCreate, actor: str, reason: Optional[str] = None) -> ConsumerKey:
    try:
        conn.execute(
            """
            INSERT INTO consumer_keys (consumer_id, node_id, virtual_key, status)
            VALUES (?, ?, ?, ?)
            """,
            (
                consumer_key.consumer_id,
                consumer_key.node_id,
                consumer_key.virtual_key,
                consumer_key.status
            )
        )
        created = get_consumer_key(conn, consumer_key.consumer_id, consumer_key.node_id)
        assert created is not None
        log_audit(conn, actor, "create_key", "consumer_key", f"{consumer_key.consumer_id}:{consumer_key.node_id}", created.model_dump(), reason)
        return created
    except sqlite3.IntegrityError as e:
        raise ValueError(f"ConsumerKey violates constraints. Ensure consumer_id and node_id exist: {e}")

def get_consumer_key(conn: sqlite3.Connection, consumer_id: str, node_id: str) -> Optional[ConsumerKey]:
    row = conn.execute(
        "SELECT * FROM consumer_keys WHERE consumer_id = ? AND node_id = ?",
        (consumer_id, node_id)
    ).fetchone()
    if row:
        return ConsumerKey.model_validate(dict(row))
    return None

def list_consumer_keys(conn: sqlite3.Connection, consumer_id: Optional[str] = None) -> List[ConsumerKey]:
    if consumer_id:
        cursor = conn.execute("SELECT * FROM consumer_keys WHERE consumer_id = ?", (consumer_id,))
    else:
        cursor = conn.execute("SELECT * FROM consumer_keys")
    return [ConsumerKey.model_validate(dict(row)) for row in cursor.fetchall()]

def update_consumer_key_status(
    conn: sqlite3.Connection,
    consumer_id: str,
    node_id: str,
    status: str,
    actor: str,
    reason: Optional[str] = None
) -> Optional[ConsumerKey]:
    old = get_consumer_key(conn, consumer_id, node_id)
    if not old:
        return None
    before_dict = old.model_dump()
    after_dict = {**before_dict, "status": status}
    
    conn.execute(
        "UPDATE consumer_keys SET status = ? WHERE consumer_id = ? AND node_id = ?",
        (status, consumer_id, node_id)
    )
    diff = {"before": before_dict, "after": after_dict}
    log_audit(conn, actor, "update_key_status", "consumer_key", f"{consumer_id}:{node_id}", diff, reason)
    return get_consumer_key(conn, consumer_id, node_id)

def update_consumer_key(
    conn: sqlite3.Connection,
    consumer_id: str,
    node_id: str,
    virtual_key: str,
    status: str,
    actor: str,
    reason: Optional[str] = None
) -> Optional[ConsumerKey]:
    """Update both the virtual_key value and status atomically, with audit trail."""
    old = get_consumer_key(conn, consumer_id, node_id)
    if not old:
        return None
    before_dict = old.model_dump()
    after_dict = {**before_dict, "virtual_key": virtual_key, "status": status}
    
    conn.execute(
        "UPDATE consumer_keys SET virtual_key = ?, status = ? WHERE consumer_id = ? AND node_id = ?",
        (virtual_key, status, consumer_id, node_id)
    )
    diff = {"before": before_dict, "after": after_dict}
    log_audit(conn, actor, "update_key", "consumer_key", f"{consumer_id}:{node_id}", diff, reason)
    return get_consumer_key(conn, consumer_id, node_id)

def delete_consumer_key(conn: sqlite3.Connection, consumer_id: str, node_id: str, actor: str, reason: Optional[str] = None) -> bool:
    key = get_consumer_key(conn, consumer_id, node_id)
    if not key:
        return False
    conn.execute("DELETE FROM consumer_keys WHERE consumer_id = ? AND node_id = ?", (consumer_id, node_id))
    log_audit(conn, actor, "delete_key", "consumer_key", f"{consumer_id}:{node_id}", key.model_dump(), reason)
    return True

# --- State Machine & Incidents Helpers ---

def set_account_cooldown(
    conn: sqlite3.Connection,
    account_id: str,
    cooldown_until: str,
    actor: str,
    reason: Optional[str] = None
) -> Optional[Account]:
    old = get_account(conn, account_id)
    if not old:
        return None
        
    before_dict = old.model_dump()
    after_dict = {**before_dict, "status": "cooldown", "cooldown_until": cooldown_until}
    
    conn.execute(
        "UPDATE accounts SET status = 'cooldown', cooldown_until = ? WHERE id = ?",
        (cooldown_until, account_id)
    )
    diff = {"before": before_dict, "after": after_dict}
    log_audit(conn, actor, "update_status", "account", account_id, diff, reason)
    return get_account(conn, account_id)

def set_endpoint_cooldown(
    conn: sqlite3.Connection,
    endpoint_id: str,
    cooldown_until: str,
    actor: str,
    reason: Optional[str] = None
) -> Optional[Endpoint]:
    old = get_endpoint(conn, endpoint_id)
    if not old:
        return None
        
    before_dict = old.model_dump()
    after_dict = {**before_dict, "status": "cooldown", "cooldown_until": cooldown_until}
    
    conn.execute(
        "UPDATE endpoints SET status = 'cooldown', cooldown_until = ? WHERE id = ?",
        (cooldown_until, endpoint_id)
    )
    diff = {"before": before_dict, "after": after_dict}
    log_audit(conn, actor, "update_status", "endpoint", endpoint_id, diff, reason)
    return get_endpoint(conn, endpoint_id)

def increment_account_failure(conn: sqlite3.Connection, account_id: str) -> int:
    conn.execute("UPDATE accounts SET failure_count = failure_count + 1 WHERE id = ?", (account_id,))
    row = conn.execute("SELECT failure_count FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return row[0] if row else 0

def increment_endpoint_failure(conn: sqlite3.Connection, endpoint_id: str) -> int:
    conn.execute("UPDATE endpoints SET failure_count = failure_count + 1 WHERE id = ?", (endpoint_id,))
    row = conn.execute("SELECT failure_count FROM endpoints WHERE id = ?", (endpoint_id,)).fetchone()
    return row[0] if row else 0

def create_incident(
    conn: sqlite3.Connection,
    target_type: str,
    target_id: str,
    state_from: str,
    state_to: str,
    reason: Optional[str] = None,
    raw_response: Optional[str] = None,
) -> Dict[str, Any]:
    import uuid
    incident_id = f"inc-{uuid.uuid4().hex[:8]}"
    conn.execute(
        """
        INSERT INTO incidents (id, target_type, target_id, state_from, state_to, reason, raw_response)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (incident_id, target_type, target_id, state_from, state_to, reason, raw_response)
    )
    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    return dict(row)

def list_incidents(
    conn: sqlite3.Connection,
    limit: int = 100,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    state_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []

    if target_type:
        clauses.append("target_type = ?")
        params.append(target_type)
    if target_id:
        clauses.append("target_id = ?")
        params.append(target_id)
    if state_to:
        clauses.append("state_to = ?")
        params.append(state_to)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    cursor = conn.execute(
        f"SELECT * FROM incidents {where} ORDER BY timestamp DESC LIMIT ?",
        params
    )
    return [dict(row) for row in cursor.fetchall()]

# --- Policy Profiles Store ---

def create_policy_profile(
    conn: sqlite3.Connection,
    profile: PolicyProfileCreate,
    actor: str,
    reason: Optional[str] = None
) -> PolicyProfile:
    try:
        conn.execute(
            """
            INSERT INTO policy_profiles (id, name, allowed_model_groups, description)
            VALUES (?, ?, ?, ?)
            """,
            (profile.id, profile.name, profile.allowed_model_groups, profile.description)
        )
        created = get_policy_profile(conn, profile.id)
        assert created is not None
        log_audit(conn, actor, "create", "policy_profile", profile.id, created.model_dump(), reason)
        return created
    except sqlite3.IntegrityError as e:
        raise ValueError(f"PolicyProfile already exists or constraint failed: {e}")

def get_policy_profile(conn: sqlite3.Connection, profile_id: str) -> Optional[PolicyProfile]:
    row = conn.execute("SELECT * FROM policy_profiles WHERE id = ?", (profile_id,)).fetchone()
    if row:
        return PolicyProfile.model_validate(dict(row))
    return None

def list_policy_profiles(conn: sqlite3.Connection) -> List[PolicyProfile]:
    cursor = conn.execute("SELECT * FROM policy_profiles")
    return [PolicyProfile.model_validate(dict(row)) for row in cursor.fetchall()]

def update_policy_profile(
    conn: sqlite3.Connection,
    profile_id: str,
    update: PolicyProfileUpdate,
    actor: str,
    reason: Optional[str] = None
) -> Optional[PolicyProfile]:
    old = get_policy_profile(conn, profile_id)
    if not old:
        return None
    fields = update.model_dump(exclude_none=True)
    if not fields:
        return old
    
    before_dict = old.model_dump()
    after_dict = {**before_dict, **fields}

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [profile_id]
    conn.execute(f"UPDATE policy_profiles SET {set_clause} WHERE id = ?", values)
    
    diff = {"before": before_dict, "after": after_dict}
    log_audit(conn, actor, "update", "policy_profile", profile_id, diff, reason)
    return get_policy_profile(conn, profile_id)

def delete_policy_profile(conn: sqlite3.Connection, profile_id: str, actor: str, reason: Optional[str] = None) -> bool:
    profile = get_policy_profile(conn, profile_id)
    if not profile:
        return False
    # Check if any consumer is referencing this profile
    cursor = conn.execute("SELECT COUNT(*) FROM consumers WHERE profile_id = ?", (profile_id,))
    if cursor.fetchone()[0] > 0:
        raise ValueError("Cannot delete policy profile; it is referenced by active consumers.")
        
    conn.execute("DELETE FROM policy_profiles WHERE id = ?", (profile_id,))
    log_audit(conn, actor, "delete", "policy_profile", profile_id, profile.model_dump(), reason)
    return True

# --- Rollouts Store ---

def create_rollout(
    conn: sqlite3.Connection,
    rollout_id: str,
    node_id: str,
    config_version: str,
    status: str,
    config_content: str,
    error_message: Optional[str] = None
) -> Rollout:
    conn.execute(
        """
        INSERT INTO rollouts (id, node_id, config_version, status, config_content, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (rollout_id, node_id, config_version, status, config_content, error_message)
    )
    row = conn.execute("SELECT * FROM rollouts WHERE id = ?", (rollout_id,)).fetchone()
    return Rollout.model_validate(dict(row))

def update_rollout_status(
    conn: sqlite3.Connection,
    rollout_id: str,
    status: str,
    error_message: Optional[str] = None
) -> Optional[Rollout]:
    conn.execute(
        "UPDATE rollouts SET status = ?, error_message = ? WHERE id = ?",
        (status, error_message, rollout_id)
    )
    row = conn.execute("SELECT * FROM rollouts WHERE id = ?", (rollout_id,)).fetchone()
    if row:
        return Rollout.model_validate(dict(row))
    return None

def get_rollout(conn: sqlite3.Connection, rollout_id: str) -> Optional[Rollout]:
    row = conn.execute("SELECT * FROM rollouts WHERE id = ?", (rollout_id,)).fetchone()
    if row:
        return Rollout.model_validate(dict(row))
    return None

def get_latest_success_rollout(conn: sqlite3.Connection, node_id: str) -> Optional[Rollout]:
    row = conn.execute(
        "SELECT * FROM rollouts WHERE node_id = ? AND status = 'success' ORDER BY timestamp DESC LIMIT 1",
        (node_id,)
    ).fetchone()
    if row:
        return Rollout.model_validate(dict(row))
    return None

def list_rollouts(conn: sqlite3.Connection, node_id: Optional[str] = None) -> List[Rollout]:
    if node_id:
        cursor = conn.execute("SELECT * FROM rollouts WHERE node_id = ? ORDER BY timestamp DESC", (node_id,))
    else:
        cursor = conn.execute("SELECT * FROM rollouts ORDER BY timestamp DESC")
    return [Rollout.model_validate(dict(row)) for row in cursor.fetchall()]

def get_unified_timeline(conn: sqlite3.Connection, limit: int = 100) -> List[Dict[str, Any]]:
    timeline = []

    # 1. Audit logs
    logs = list_audit_logs(conn, limit)
    for log in logs:
        timeline.append({
            "event_type": "audit",
            "id": str(log["id"]),
            "timestamp": log["timestamp"],
            "actor": log["actor"],
            "action": log["action"],
            "target_type": log["target_type"],
            "target_id": log["target_id"],
            "details": {
                "changes": log["changes"],
                "reason": log["reason"]
            }
        })

    # 2. Incidents
    incidents = list_incidents(conn, limit=limit)
    for inc in incidents:
        timeline.append({
            "event_type": "incident",
            "id": inc["id"],
            "timestamp": inc["timestamp"],
            "actor": "system",
            "action": "state_transition",
            "target_type": inc["target_type"],
            "target_id": inc["target_id"],
            "details": {
                "state_from": inc["state_from"],
                "state_to": inc["state_to"],
                "reason": inc["reason"],
                "raw_response": inc["raw_response"]
            }
        })

    # 3. Rollouts
    cursor = conn.execute(
        "SELECT id, node_id, config_version, status, error_message, timestamp FROM rollouts ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    )
    for row in cursor.fetchall():
        r = dict(row)
        timeline.append({
            "event_type": "rollout",
            "id": r["id"],
            "timestamp": r["timestamp"],
            "actor": "rollout-orchestrator",
            "action": f"deploy_{r['status']}",
            "target_type": "node",
            "target_id": r["node_id"],
            "details": {
                "config_version": r["config_version"],
                "status": r["status"],
                "error_message": r["error_message"]
            }
        })

    # Sort all by timestamp descending
    timeline.sort(key=lambda x: x["timestamp"], reverse=True)
    return timeline[:limit]



