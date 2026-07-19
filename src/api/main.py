import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from src.config.db import init_db
from src.api import routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run database schema migrations on startup."""
    init_db()
    yield

app = FastAPI(
    title="LiteLLM Control Plane API",
    description="Admin and Control Plane API for LiteLLM network state, registries, and policies.",
    version="0.1.0",
    lifespan=lifespan
)

# API Key security scheme definition
API_KEY_NAME = "X-Admin-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key: str = Security(api_key_header)):
    """Validate incoming X-Admin-API-Key header against the configuration."""
    expected_key = os.getenv("CONTROL_PLANE_ADMIN_KEY", "admin-api-key-123")
    if not api_key or api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    return api_key

@app.get("/health", tags=["system"])
def health():
    """Unauthenticated health status probe endpoint."""
    return {"status": "healthy"}

# Register authenticated registry and audit routes
app.include_router(routes.router, dependencies=[Depends(get_api_key)])

