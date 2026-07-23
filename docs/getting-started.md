# Setup Guide: Multi-Node Configuration & Deployment

This guide provides step-by-step instructions to configure, register, deploy, and verify a remote Tailscale-connected LiteLLM node using the control plane.

---

## 💡 Core Concept: Model Parameter Mapping

One of the most important concepts to understand is how model names in the Control Plane database map to the generated `config.yaml` file. This decoupling allows you to change the underlying model without changing client-side code.

### Parameter Mapping Table

| Control Plane DB Field (Model Registry) | Example Value | Target YAML Parameter | Role |
| :--- | :--- | :--- | :--- |
| **`id`** | `gemma4-31b` | *N/A (Database Key)* | Unique identifier for internal DB queries and endpoints. |
| **`logical_group`** | `gemma-latest` | `model_name` | **Logical Name (Client Alias)**: The model name requested by upstream client apps (e.g., `model="gemma-latest"`). |
| **`name`** | `gemma4:31b` | `model` | **Physical Name (Upstream)**: The real model tag forwarded to the provider (e.g., `ollama/gemma4:31b` or `gemma4:31b`). |

### Visualization of YAML Compilation

```text
Control Plane Database:
┌────────────────────────────────────────────────────────┐
│ Model ID: gemma4-31b                                   │
│   ├── logical_group: "gemma-latest" ───────────────────┼──┐
│   └── name:          "gemma4:31b"                      │  │
└────────────────────────────────────────────────────────┘  │
                                                            │
Generated config.yaml on Node (gw-kr):                      │
┌────────────────────────────────────────────────────────┐  │
│ model_list:                                            │  │
│   - model_name: "gemma-latest"   ◄─────────────────────┼──┘ (Used by Client Apps)
│     litellm_params:                                    │
│       model: "ollama/gemma4:31b" ◄─────────────────────┼──┐ (Sent to Ollama Cloud)
│       api_base: "https://ollama.com"                   │  │
│       api_key: "ffbc5cd50a6741..."                     │  │
└────────────────────────────────────────────────────────┘  │
                                                            │
Upstream Provider (Ollama Cloud):                           │
┌────────────────────────────────────────────────────────┐  │
│ Runs Model: "ollama/gemma4:31b" ◄──────────────────────┼──┘
└────────────────────────────────────────────────────────┘
```

---

## Step 1: Environment Setup

Do not store secrets in the Git repository. Instead, configure them in a local `.env` file at the root of the control plane project.

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Populate the `.env` file with your credentials:
   - `CONTROL_PLANE_ADMIN_KEY`: The API key you will use to authenticate with the control plane (Swagger UI).
   - `DOPPLER_TOKEN_<PROJECT>_<CONFIG>`: The service token generated from the Doppler dashboard (under the **Access** tab of your specific config).
   - `LITELLM_MASTER_KEY_<NODE_ID>`: The master key of the corresponding LiteLLM proxy node (Node ID must be in uppercase, with special characters replaced by underscores).

---

## Step 2: Start the Control Plane API

1. Run the Uvicorn server (which automatically loads the `.env` variables and initializes the SQLite database `control_plane.db` on startup):
   - **Windows (PowerShell)**:
     ```powershell
     .venv\Scripts\python.exe -m uvicorn src.api.main:app --port 8000 --reload
     ```
   - **Linux/macOS**:
     ```bash
     .venv/bin/python -m uvicorn src.api.main:app --port 8000 --reload
     ```
2. Open your browser and navigate to the interactive documentation:
   `http://127.0.0.1:8000/docs`

---

## Step 3: Register Resources (Desired State)

In the Swagger UI, click **Authorize** in the top right, enter your `CONTROL_PLANE_ADMIN_KEY`, and execute the following API calls in sequence:

### 1. Register the Node (`POST /registry/nodes`)
Register your remote VPS running LiteLLM. Provide its Tailscale IP address and port:
```json
{
  "id": "gw-kr",
  "name": "Gateway Korea",
  "host": "100.84.189.115",
  "port": 4000,
  "region": "kr",
  "role": "proxy"
}
```

### 2. Register the Provider (`POST /registry/providers`)
Declare the upstream API provider:
```json
{
  "id": "ollama-cloud",
  "name": "Ollama Cloud",
  "type": "ollama"
}
```

### 3. Register Accounts (`POST /registry/accounts`)
Register your API keys as accounts referencing your Doppler secrets. Register both primary and backup accounts for high-availability:
* **Primary Account**:
  ```json
  {
    "id": "ollama-primary",
    "name": "Ollama Primary Account",
    "provider_id": "ollama-cloud",
    "secret_ref": "doppler://all_free_api_tokens/prd_kr/OLLAMA_API_KEY",
    "status": "active"
  }
  ```
* **Backup Account**:
  ```json
  {
    "id": "ollama-backup",
    "name": "Ollama Backup Account",
    "provider_id": "ollama-cloud",
    "secret_ref": "doppler://all_free_api_tokens/prd_kr/OLLAMA_API_BKUP_KEY",
    "status": "active"
  }
  ```

### 4. Register the Model (`POST /registry/models`)
Define the upstream model running on the provider and map it to a logical group:
```json
{
  "id": "gemma4-31b",
  "name": "gemma4:31b",
  "logical_group": "gemma-latest",
  "capability_chat": true,
  "capability_stream": true,
  "capability_tools": true,
  "capability_embeddings": false
}
```

### 5. Register Endpoints (`POST /registry/endpoints`)
Bind the Model and Accounts to the Node, defining priorities for failover routing (lower priority number runs first):
* **Primary Endpoint**:
  ```json
  {
    "id": "ep-gemma4-primary",
    "node_id": "gw-kr",
    "account_id": "ollama-primary",
    "model_id": "gemma4-31b",
    "priority": 1,
    "weight": 100,
    "status": "active"
  }
  ```
* **Backup Endpoint**:
  ```json
  {
    "id": "ep-gemma4-backup",
    "node_id": "gw-kr",
    "account_id": "ollama-backup",
    "model_id": "gemma4-31b",
    "priority": 2,
    "weight": 100,
    "status": "active"
  }
  ```

---

## Step 4: Deploy the Configuration

1. Trigger the rollout by calling **`POST /rollouts/deploy/{node_id}`**:
   - `node_id`: `gw-kr`
   - `config_filepath`: `C:/temp/gw-kr-config.yaml`
2. Open the generated file at `C:/temp/gw-kr-config.yaml` and copy its entire content.
3. SSH into the remote VPS, and overwrite the existing `config.yaml` of the LiteLLM proxy:
   ```bash
   nano /home/ubuntu/litellm-gateway/config.yaml
   ```
4. Restart the LiteLLM service on the VPS to apply the changes:
   ```bash
   sudo systemctl restart litellm
   ```

---

## Step 5: Verify End-to-End Routing

Perform a direct chat completion request to the remote LiteLLM node using its Master Key:
```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <LITELLM_MASTER_KEY>" \
  -d '{
    "model": "gemma-latest",
    "messages": [
      {"role": "user", "content": "Hello! Introduce yourself briefly."}
    ]
  }'
```

---

## Step 6: Enable Webhook Auto-Reporting

To allow LiteLLM to report usage metrics and error codes back to the control plane, configure the logging webhook:

1. In the remote VPS shell, export the control plane URL as an environment variable:
   ```bash
   export LITELLM_LOGGING_WEBHOOK="http://<CONTROL_PLANE_TAILSCALE_IP>:8000/events/callback"
   ```
2. Restart the LiteLLM service:
   ```bash
   sudo systemctl restart litellm
   ```
   Now, all requests processed by the VPS will be automatically logged in the control plane's audit and state timeline!
