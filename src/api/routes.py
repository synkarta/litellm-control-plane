from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from src.config.db import get_db_dep
from src.registry import store, key_manager
from src.registry.models import (
    Node, NodeCreate, NodeUpdate,
    Provider, ProviderCreate, ProviderUpdate,
    Model, ModelCreate, ModelUpdate,
    Account, AccountCreate,
    Endpoint, EndpointCreate,
    Consumer, ConsumerCreate, ConsumerUpdate,
    ConsumerKey,
    PolicyProfile, PolicyProfileCreate, PolicyProfileUpdate,
    Rollout
)
from src.health import manager as health_manager
from src.events import ingestion

router = APIRouter()
callback_router = APIRouter()

# Actor names reserved for internal system components.
# External callers must not claim these identities via X-Actor.
_RESERVED_ACTORS = frozenset({
    "system",
    "reconcile-worker",
    "probe",
    "probe-engine",
    "key-manager",
    "callback-ingest",
    "rollout-orchestrator",
})

def get_actor(x_actor: Optional[str] = Header(None, alias="X-Actor")) -> str:
    """Resolve the actor identity from the X-Actor request header.

    Defaults to 'admin-api'. Rejects reserved internal actor names to prevent
    audit log spoofing.
    """
    if x_actor and x_actor in _RESERVED_ACTORS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Actor name '{x_actor}' is reserved for internal system use."
        )
    return x_actor or "admin-api"

# --- Nodes Endpoints ---

@router.post("/registry/nodes", response_model=Node, tags=["nodes"])
def create_node(node: NodeCreate, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    try:
        return store.create_node(conn, node, actor=actor)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/registry/nodes", response_model=List[Node], tags=["nodes"])
def list_nodes(conn = Depends(get_db_dep)):
    return store.list_nodes(conn)

@router.get("/registry/nodes/{id}", response_model=Node, tags=["nodes"])
def get_node(id: str, conn = Depends(get_db_dep)):
    node = store.get_node(conn, id)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return node

@router.delete("/registry/nodes/{id}", tags=["nodes"])
def delete_node(id: str, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    if not store.delete_node(conn, id, actor=actor):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return {"detail": "Node deleted"}

@router.patch("/registry/nodes/{id}", response_model=Node, tags=["nodes"])
def update_node(id: str, update: NodeUpdate, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    node = store.update_node(conn, id, update, actor=actor)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return node


# --- Providers Endpoints ---

@router.post("/registry/providers", response_model=Provider, tags=["providers"])
def create_provider(provider: ProviderCreate, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    try:
        return store.create_provider(conn, provider, actor=actor)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/registry/providers", response_model=List[Provider], tags=["providers"])
def list_providers(conn = Depends(get_db_dep)):
    return store.list_providers(conn)

@router.get("/registry/providers/{id}", response_model=Provider, tags=["providers"])
def get_provider(id: str, conn = Depends(get_db_dep)):
    provider = store.get_provider(conn, id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return provider

@router.delete("/registry/providers/{id}", tags=["providers"])
def delete_provider(id: str, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    try:
        if not store.delete_provider(conn, id, actor=actor):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        return {"detail": "Provider deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.patch("/registry/providers/{id}", response_model=Provider, tags=["providers"])
def update_provider(id: str, update: ProviderUpdate, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    provider = store.update_provider(conn, id, update, actor=actor)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return provider


# --- Models Endpoints ---

@router.post("/registry/models", response_model=Model, tags=["models"])
def create_model(model: ModelCreate, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    try:
        return store.create_model(conn, model, actor=actor)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/registry/models", response_model=List[Model], tags=["models"])
def list_models(conn = Depends(get_db_dep)):
    return store.list_models(conn)

@router.get("/registry/models/{id}", response_model=Model, tags=["models"])
def get_model(id: str, conn = Depends(get_db_dep)):
    model = store.get_model(conn, id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return model

@router.delete("/registry/models/{id}", tags=["models"])
def delete_model(id: str, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    try:
        if not store.delete_model(conn, id, actor=actor):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        return {"detail": "Model deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.patch("/registry/models/{id}", response_model=Model, tags=["models"])
def update_model(id: str, update: ModelUpdate, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    try:
        model = store.update_model(conn, id, update, actor=actor)
        if not model:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        return model
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Accounts Endpoints ---

@router.post("/registry/accounts", response_model=Account, tags=["accounts"])
def create_account(account: AccountCreate, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    try:
        return store.create_account(conn, account, actor=actor)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/registry/accounts", response_model=List[Account], tags=["accounts"])
def list_accounts(conn = Depends(get_db_dep)):
    return store.list_accounts(conn)

@router.get("/registry/accounts/{id}", response_model=Account, tags=["accounts"])
def get_account(id: str, conn = Depends(get_db_dep)):
    account = store.get_account(conn, id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account

@router.post("/registry/accounts/{id}/status", response_model=Account, tags=["accounts"])
def update_account_status(
    id: str,
    status_val: str = Query(..., alias="status"),
    actor: str = Depends(get_actor),
    conn = Depends(get_db_dep)
):
    if status_val not in ["active", "inactive", "cooldown", "disabled"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status value")
    account = store.update_account_status(conn, id, status_val, actor=actor)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account

@router.delete("/registry/accounts/{id}", tags=["accounts"])
def delete_account(id: str, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    try:
        if not store.delete_account(conn, id, actor=actor):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        return {"detail": "Account deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Endpoints Endpoints ---

@router.post("/registry/endpoints", response_model=Endpoint, tags=["endpoints"])
def create_endpoint(endpoint: EndpointCreate, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    try:
        return store.create_endpoint(conn, endpoint, actor=actor)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/registry/endpoints", response_model=List[Endpoint], tags=["endpoints"])
def list_endpoints(conn = Depends(get_db_dep)):
    return store.list_endpoints(conn)

@router.get("/registry/endpoints/{id}", response_model=Endpoint, tags=["endpoints"])
def get_endpoint(id: str, conn = Depends(get_db_dep)):
    endpoint = store.get_endpoint(conn, id)
    if not endpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    return endpoint

@router.post("/registry/endpoints/{id}/routing", response_model=Endpoint, tags=["endpoints"])
def update_endpoint_routing(
    id: str,
    priority: Optional[int] = Query(None),
    weight: Optional[int] = Query(None),
    actor: str = Depends(get_actor),
    conn = Depends(get_db_dep)
):
    endpoint = store.update_endpoint_routing(conn, id, priority, weight, actor=actor)
    if not endpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    return endpoint

@router.post("/registry/endpoints/{id}/status", response_model=Endpoint, tags=["endpoints"])
def update_endpoint_status(
    id: str,
    status_val: Optional[str] = Query(None, alias="status"),
    manual_override: Optional[str] = Query(None),
    actor: str = Depends(get_actor),
    conn = Depends(get_db_dep)
):
    if status_val and status_val not in ["active", "degraded", "cooldown", "disabled"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status value")
    if manual_override and manual_override not in ["none", "force-active", "force-disabled"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid manual_override value")
        
    endpoint = store.update_endpoint_status(conn, id, status_val, manual_override, actor=actor)
    if not endpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    return endpoint

@router.delete("/registry/endpoints/{id}", tags=["endpoints"])
def delete_endpoint(id: str, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    if not store.delete_endpoint(conn, id, actor=actor):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    return {"detail": "Endpoint deleted"}


# --- Consumers Endpoints ---

@router.post("/registry/consumers", response_model=Consumer, tags=["consumers"])
def create_consumer(consumer: ConsumerCreate, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    try:
        res = store.create_consumer(conn, consumer, actor=actor)
        key_manager.sync_consumer_to_all_nodes(conn, res.id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/registry/consumers", response_model=List[Consumer], tags=["consumers"])
def list_consumers(conn = Depends(get_db_dep)):
    return store.list_consumers(conn)

@router.get("/registry/consumers/{id}", response_model=Consumer, tags=["consumers"])
def get_consumer(id: str, conn = Depends(get_db_dep)):
    consumer = store.get_consumer(conn, id)
    if not consumer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consumer not found")
    return consumer

@router.patch("/registry/consumers/{id}", response_model=Consumer, tags=["consumers"])
def update_consumer(id: str, update: ConsumerUpdate, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    res = store.update_consumer(conn, id, update, actor=actor)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consumer not found")
    key_manager.sync_consumer_to_all_nodes(conn, res.id)
    return res

@router.delete("/registry/consumers/{id}", tags=["consumers"])
def delete_consumer(id: str, actor: str = Depends(get_actor), conn = Depends(get_db_dep)):
    # M3 fix: check existence first before any remote operations
    if not store.get_consumer(conn, id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consumer not found")
    key_manager.delete_consumer_from_all_nodes(conn, id)
    store.delete_consumer(conn, id, actor=actor)
    return {"detail": "Consumer deleted"}

@router.get("/registry/consumers/{id}/keys", response_model=List[ConsumerKey], tags=["consumers"])
def list_consumer_keys(id: str, conn = Depends(get_db_dep)):
    return store.list_consumer_keys(conn, consumer_id=id)



# --- Audit Logs Endpoints ---

@router.get("/audit-logs", tags=["audit"])
def list_audit_logs(limit: int = Query(100, ge=1, le=1000), conn = Depends(get_db_dep)):
    return store.list_audit_logs(conn, limit=limit)


# --- Health & Ingestion Endpoints ---

@callback_router.post("/events/callback", tags=["events"])
def ingest_event_callback(
    payload: Union[List[Dict[str, Any]], Dict[str, Any]],
    conn = Depends(get_db_dep)
):
    """
    Webhook endpoint to ingest events from LiteLLM proxy nodes.
    Requires X-Callback-Token (separate from the admin API key).
    Validates that referenced endpoint_id and account_id exist before processing.
    """
    from src.registry import store as _store
    return ingestion.ingest_event_callback(payload, conn, validator=_store)

@router.get("/health/summary", tags=["health"])
def health_summary(conn = Depends(get_db_dep)):
    """
    Query consolidated health state across all nodes, accounts, and endpoints.
    """
    return health_manager.get_health_summary(conn)

@router.get("/health/incidents", tags=["health"])
def health_incidents(
    limit: int = Query(100, ge=1, le=1000),
    target_type: Optional[str] = Query(None, description="Filter by entity type: 'account' or 'endpoint'"),
    target_id: Optional[str] = Query(None, description="Filter by a specific account or endpoint ID"),
    state_to: Optional[str] = Query(None, description="Filter by destination state, e.g. 'disabled', 'cooldown', 'degraded'"),
    conn = Depends(get_db_dep)
):
    """
    Retrieve logs of health state transitions and provider failures.
    Use filters to drill down to a specific resource or failure type for operator review.
    """
    return health_manager.get_incidents_list(
        conn,
        limit=limit,
        target_type=target_type,
        target_id=target_id,
        state_to=state_to,
    )

@router.get("/timeline", tags=["health"])
def unified_timeline(
    limit: int = Query(100, ge=1, le=1000),
    conn = Depends(get_db_dep)
):
    """
    Retrieve unified timeline of health incidents, audit logs, and rollout events.
    Returns events sorted in chronological order.
    """
    return store.get_unified_timeline(conn, limit=limit)

# L3: Per-entity health detail endpoints for operator drill-down

@router.get("/health/accounts/{id}", tags=["health"])
def health_account_detail(id: str, conn = Depends(get_db_dep)):
    """
    Return health detail for a specific account: current state, cooldown info,
    failure count, and recent incident history. Intended for operator review
    when verifying a disabled or degraded account.
    """
    acc = store.get_account(conn, id)
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    incidents = store.list_incidents(conn, target_type="account", target_id=id, limit=20)
    return {
        "account": {
            "id": acc.id,
            "name": acc.name,
            "provider_id": acc.provider_id,
            "secret_ref": acc.secret_ref,
            "status": acc.status,
            "cooldown_until": acc.cooldown_until,
            "failure_count": acc.failure_count,
        },
        "recent_incidents": incidents,
    }

@router.get("/health/endpoints/{id}", tags=["health"])
def health_endpoint_detail(id: str, conn = Depends(get_db_dep)):
    """
    Return health detail for a specific endpoint: current state, cooldown info,
    failure count, manual override, and recent incident history.
    """
    ep = store.get_endpoint(conn, id)
    if not ep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    incidents = store.list_incidents(conn, target_type="endpoint", target_id=id, limit=20)
    return {
        "endpoint": {
            "id": ep.id,
            "node_id": ep.node_id,
            "account_id": ep.account_id,
            "model_id": ep.model_id,
            "status": ep.status,
            "manual_override": ep.manual_override,
            "cooldown_until": ep.cooldown_until,
            "failure_count": ep.failure_count,
        },
        "recent_incidents": incidents,
    }

# L5: Explicit operator enable endpoints

@router.post("/registry/accounts/{id}/enable", response_model=Account, tags=["accounts"])
def enable_account(
    id: str,
    actor: str = Depends(get_actor),
    conn = Depends(get_db_dep)
):
    """
    Operator action: re-enable a disabled or cooldown account.
    Clears cooldown_until and resets failure_count to 0.
    Use after verifying provider feedback via GET /health/accounts/{id}.
    """
    acc = store.get_account(conn, id)
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    updated = store.update_account_status(
        conn, id, "active", actor=actor,
        reason="Manual re-enable by operator"
    )
    return updated

@router.post("/registry/endpoints/{id}/enable", response_model=Endpoint, tags=["endpoints"])
def enable_endpoint(
    id: str,
    actor: str = Depends(get_actor),
    conn = Depends(get_db_dep)
):
    """
    Operator action: re-enable a disabled or cooldown endpoint.
    Clears cooldown_until and resets failure_count to 0.
    Use after verifying provider feedback via GET /health/endpoints/{id}.
    """
    ep = store.get_endpoint(conn, id)
    if not ep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    updated = store.update_endpoint_status(
        conn, id, status="active", manual_override=None,
        actor=actor, reason="Manual re-enable by operator"
    )
    return updated

# --- Policy Profiles Endpoints ---

@router.post("/registry/policies", response_model=PolicyProfile, tags=["policies"])
def create_policy_profile(
    profile: PolicyProfileCreate,
    actor: str = Depends(get_actor),
    conn = Depends(get_db_dep)
):
    try:
        return store.create_policy_profile(conn, profile, actor=actor)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/registry/policies", response_model=List[PolicyProfile], tags=["policies"])
def list_policy_profiles(conn = Depends(get_db_dep)):
    return store.list_policy_profiles(conn)

@router.get("/registry/policies/{id}", response_model=PolicyProfile, tags=["policies"])
def get_policy_profile(id: str, conn = Depends(get_db_dep)):
    profile = store.get_policy_profile(conn, id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy profile not found")
    return profile

@router.patch("/registry/policies/{id}", response_model=PolicyProfile, tags=["policies"])
def update_policy_profile(
    id: str,
    update: PolicyProfileUpdate,
    actor: str = Depends(get_actor),
    conn = Depends(get_db_dep)
):
    profile = store.update_policy_profile(conn, id, update, actor=actor)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy profile not found")
    return profile

@router.delete("/registry/policies/{id}", tags=["policies"])
def delete_policy_profile(
    id: str,
    actor: str = Depends(get_actor),
    conn = Depends(get_db_dep)
):
    try:
        if not store.delete_policy_profile(conn, id, actor=actor):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy profile not found")
        return {"detail": "Policy profile deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# --- Rollouts & Drift Endpoints ---

from src.secrets.doppler import DopplerResolver
from src.config.generator import ConfigGenerator
from src.rollout.orchestrator import RolloutOrchestrator

resolver = DopplerResolver()
generator = ConfigGenerator(resolver)
orchestrator = RolloutOrchestrator(generator)

@router.post("/rollouts/deploy/{node_id}", response_model=Rollout, tags=["rollouts"])
def deploy_config(
    node_id: str,
    config_filepath: str = Query(..., description="Target file path on disk to write the config to"),
    timeout_sec: float = Query(10.0, description="Verification timeout in seconds"),
    conn = Depends(get_db_dep)
):
    try:
        res = orchestrator.deploy_config(
            conn=conn,
            node_id=node_id,
            config_filepath=config_filepath,
            timeout_sec=timeout_sec
        )
        # Fetch the created rollout record
        rollout = store.get_rollout(conn, res["rollout_id"])
        if not rollout:
            raise HTTPException(status_code=500, detail="Rollout record not found after successful deployment")
        return rollout
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/rollouts/history/{node_id}", response_model=List[Rollout], tags=["rollouts"])
def list_rollout_history(node_id: str, conn = Depends(get_db_dep)):
    node = store.get_node(conn, node_id)
    if not node:
        raise HTTPException(status_code=status.HTTP_444_NOT_FOUND if hasattr(status, "HTTP_444_NOT_FOUND") else 404, detail="Node not found")
    return store.list_rollouts(conn, node_id=node_id)

@router.get("/rollouts/drift/{node_id}", tags=["rollouts"])
def detect_drift(
    node_id: str,
    config_filepath: str = Query(..., description="Disk path of the active config file"),
    conn = Depends(get_db_dep)
):
    try:
        return orchestrator.detect_drift(conn, node_id, config_filepath)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

