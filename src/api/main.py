import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables from .env file at startup
load_dotenv()

from fastapi import FastAPI, Depends, Security, HTTPException, status, Response
from fastapi.security.api_key import APIKeyHeader
from src.config.db import init_db, get_db
from src.api import routes
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

ADMIN_KEY = os.getenv("CONTROL_PLANE_ADMIN_KEY")
if not ADMIN_KEY:
    raise RuntimeError("CONTROL_PLANE_ADMIN_KEY environment variable is required")

logger = logging.getLogger("main")

async def _reconcile_loop(interval_sec: int = 30) -> None:
    """Background task: periodically reconcile expired cooldowns and trigger probes."""
    # Lazy import to avoid circular dependency at module load
    from src.health.probe import ProbeEngine
    from src.secrets.doppler import DopplerResolver

    resolver = DopplerResolver()
    engine = ProbeEngine(resolver=resolver)

    while True:
        await asyncio.sleep(interval_sec)
        try:
            # 1. Reconcile cooldowns in thread (opens its own connection)
            def run_cooldowns():
                with get_db() as conn:
                    engine.reconcile_cooldowns(conn, "reconcile-worker")
            await asyncio.to_thread(run_cooldowns)
            
            # 2. Get active nodes list quickly from event loop thread
            node_ids = []
            with get_db() as conn:
                from src.registry import store
                nodes = store.list_nodes(conn)
                node_ids = [n.id for n in nodes if n.status == "active"]

            # 3. Auto-reconcile config and key drift for each active node in thread (opens its own connection)
            from src.api.routes import orchestrator
            for node_id in node_ids:
                def run_reconcile(nid=node_id):
                    with get_db() as conn:
                        orchestrator.reconcile_node(conn, nid)
                await asyncio.to_thread(run_reconcile)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Reconcile loop error: {e}", exc_info=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB schema and launch background reconcile loop. Shutdown: cancel loop."""
    init_db()
    task = asyncio.create_task(_reconcile_loop(interval_sec=30))
    logger.info("Background reconcile loop started (interval=30s)")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("Background reconcile loop stopped")

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
    if not api_key or api_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    return api_key

@app.get("/health", tags=["system"])
def health():
    """Unauthenticated health status probe endpoint."""
    return {"status": "healthy"}

@app.get("/metrics", tags=["system"])
def metrics():
    """Expose Prometheus metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Register authenticated registry and audit routes
app.include_router(routes.router, dependencies=[Depends(get_api_key)])


