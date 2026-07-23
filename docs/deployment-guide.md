# Deployment Guide

This guide details how to deploy `litellm-control-plane` and its managed `LiteLLM` nodes.

## 1. Local Native Setup (Testing & Development)

The MVP allows running the control plane natively on your local machine using an embedded SQLite database.

### Prerequisites
- Python 3.10+
- `pip install -r requirements.txt` (including FastAPI, HTTPX, Pydantic, etc.)
- LiteLLM CLI installed in the same environment (`pip install litellm`)

### Bootstrap the Control Plane
1. Ensure the required admin key is set.
   ```bash
   export CONTROL_PLANE_ADMIN_KEY="my-secret-key"
   ```
2. Start the API Server. The `control_plane.db` SQLite database is automatically created and initialized on startup.
   ```bash
   uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
   ```

### Connecting LiteLLM
In local mode, you can use the adapter's `start_subprocess` helper or run LiteLLM manually:
```bash
# Provide the LiteLLM Master Key to allow the control plane to orchestrate it
export LITELLM_MASTER_KEY="sk-master-key"
litellm --config my-generated-config.yaml --port 4000
```
Then, register the node in the Control Plane API pointing to `http://127.0.0.1:4000`.

## 2. Secrets & Doppler Injection

In all environments, raw keys must not be placed into `.env` files. You must use Doppler.

1. **Install Doppler CLI**: Follow [Doppler installation docs](https://docs.doppler.com/docs/install-cli).
2. **Authenticate**: 
   ```bash
   doppler login
   ```
3. **Run with Doppler**:
   ```bash
   export CONTROL_PLANE_ADMIN_KEY="my-secret-key"
   doppler run -- uvicorn src.api.main:app --host 127.0.0.1 --port 8000
   ```
   *Alternatively*, inject the specific service token:
   ```bash
   export DOPPLER_TOKEN_LITELLM_INFRA_PRD_US="dp.st.prd...."
   export CONTROL_PLANE_ADMIN_KEY="my-secret-key"
   uvicorn src.api.main:app ...
   ```

## 3. Production Deployment Notes (Future Milestones)

- **Database**: The SQLite engine should be replaced with PostgreSQL for multi-controller High Availability (HA).
- **Docker**: Containerize the control plane.
- **Tailscale**: Place the control plane and all LiteLLM nodes on a private Tailnet. Ensure API calls to the LiteLLM proxy (`/key/generate`) do not route over the public internet.

---

## Next Steps

Once the control plane is deployed and running, refer to the [Getting Started Guide](getting-started.md) to register your nodes, providers, models, and accounts step-by-step.

