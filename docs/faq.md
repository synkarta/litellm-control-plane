# FAQ: LiteLLM Control Plane

This document answers common architectural and operational questions regarding the LiteLLM Control Plane.

---

### Q1: Why does LiteLLM return `DB not connected` when generating virtual keys?
* **Cause**: LiteLLM's dynamic Virtual Keys feature (`POST /key/generate`) requires a persistent database (like PostgreSQL) connected to the LiteLLM proxy node. If your LiteLLM instance is running in stateless mode (without a PostgreSQL backend), LiteLLM cannot store or validate dynamic keys and will throw a `500 DB not connected` error.
* **Workaround**: You can bypass the virtual key requirement by using the node's static **Master Key** (e.g., `LITELLM_MASTER_KEY_GW_KR`) directly in the client app's `Authorization` header. Model routing and failover will still work perfectly.
* **Solution**: If you want to use dynamic keys and budgets, configure a PostgreSQL database on the VPS, set the `DATABASE_URL` environment variable for LiteLLM, and restart the service.

---

### Q2: Why shouldn't I manually edit `config.yaml` on the VPS?
* **Answer**: The control plane governs the state of all nodes. It runs a background **Drift Detection & Reconciliation Loop** (every 30 seconds). If you manually edit the `config.yaml` file on the VPS:
  1. The control plane will detect a config mismatch (drift).
  2. The control plane will automatically compile the desired state from the database and **overwrite your manual changes** on the next reconciliation run.
* **Correct Flow**: Always use the control plane APIs (Swagger UI or admin console) to update nodes, accounts, models, or endpoints, then trigger a rollout via `POST /rollouts/deploy/{node_id}`.

---

### Q3: What is the difference between `model` and `model_name` in the generated YAML?
* **Answer**:
  - **`model_name` (Logical Name / Client Alias)**: Map from `logical_group` in the DB. This is the identifier client applications use to call the API (e.g., `model="gemma-latest"`).
  - **`model` (Physical Name / Upstream Tag)**: Map from `name` in the DB. This is the actual model name sent to the upstream provider (e.g., `ollama/gemma4:31b`).
* **Why Decouple?**: Decoupling prevents client code modification when changing backend models. If you upgrade from `gemma4:31b` to `gemma5:31b`, you only update the model definition in the control plane. Upstream clients can continue to request `gemma-latest` without modifying their codebase.

---

### Q4: How does the control plane find the master key for a node?
* **Answer**: The control plane uses a specific environment variable naming convention to fetch node master keys from the local `.env` or system environment:
  - Format: `LITELLM_MASTER_KEY_<NODE_ID>`
  - The `<NODE_ID>` must be converted to uppercase, with hyphens and special characters replaced by underscores.
  - **Example**: For node ID `gw-kr`, the environment variable must be named `LITELLM_MASTER_KEY_GW_KR`.

---

### Q5: Does the control plane need to run all the time?
* **Answer**: 
  - **For raw request execution**: **No**. LiteLLM nodes process inference requests independently using their local `config.yaml`. If the control plane goes offline, LiteLLM continues serving requests using the last deployed configuration.
  - **For operations and governance**: **Yes**. The control plane is a daemon service that must remain active to:
    1. Monitor node and account health.
    2. Automatically failover and update configs if a provider account is depleted or rate-limited.
    3. Ingest callback/spend events.
    4. Serve service discovery requests (e.g., `/health/summary`).

---

### Q6: Who handles routing between different resource nodes?
* **Answer**: 
  - **Per-request failover/retries**: Handled entirely inside the **LiteLLM node** (data plane) on the fly for minimal latency.
  - **Multi-node traffic distribution**: Handled by your **Network Layer** (e.g., a Global Load Balancer like Nginx/Cloudflare, Geo-DNS, or client-side regional endpoints).
  - **Topology governance & configuration**: Handled by the **Control Plane** (calculating account status, maintaining config consistency, and updating configs globally).

---

### Q7: Where does the Doppler token go? Do the remote VPS nodes need Doppler installed?
* **Answer**: Doppler is only accessed by the control plane.
  - The control plane queries Doppler to retrieve and decrypt secrets (API Keys, bases).
  - The control plane compiles these decrypted keys directly into the generated `config.yaml` file.
  - The remote VPS nodes only receive the static YAML file and do not need Doppler installed, keeping VPS deployments simple and secure.
