import json
import sqlite3
from typing import Any, Dict, List, Optional
from src.audit.logger import log_audit
from src.registry.models import (
    Node, NodeCreate, NodeUpdate,
    Provider, ProviderCreate, ProviderUpdate,
    Model, ModelCreate, ModelUpdate,
    Account, AccountCreate,
    Endpoint, EndpointCreate
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
    
    conn.execute("UPDATE accounts SET status = ? WHERE id = ?", (status, account_id))
    new = get_account(conn, account_id)
    assert new is not None
    diff = {"before": old.model_dump(), "after": new.model_dump()}
    log_audit(conn, actor, "update_status", "account", account_id, diff, reason)
    return new

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
    
    conn.execute(
        "UPDATE endpoints SET status = ?, manual_override = ? WHERE id = ?",
        (new_status, new_override, endpoint_id)
    )
    new = get_endpoint(conn, endpoint_id)
    assert new is not None
    diff = {"before": old.model_dump(), "after": new.model_dump()}
    log_audit(conn, actor, "update_status", "endpoint", endpoint_id, diff, reason)
    return new

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
