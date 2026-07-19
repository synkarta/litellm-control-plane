from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from src.config.db import get_db_dep
from src.registry import store
from src.registry.models import (
    Node, NodeCreate, NodeUpdate,
    Provider, ProviderCreate, ProviderUpdate,
    Model, ModelCreate, ModelUpdate,
    Account, AccountCreate,
    Endpoint, EndpointCreate
)

router = APIRouter()

def get_actor(x_actor: Optional[str] = Header(None, alias="X-Actor")) -> str:
    """Resolve the actor identity from the X-Actor request header, defaulting to 'admin-api'."""
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


# --- Audit Logs Endpoints ---

@router.get("/audit-logs", tags=["audit"])
def list_audit_logs(limit: int = Query(100, ge=1, le=1000), conn = Depends(get_db_dep)):
    return store.list_audit_logs(conn, limit=limit)
