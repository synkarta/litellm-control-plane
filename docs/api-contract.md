# API Contract

This document outlines the REST API exposed by `litellm-control-plane`. The API allows for CRUD operations on inventory resources, rollout orchestration, health incident management, and observability metrics.

All endpoints are intended for internal operators or automation scripts (CI/CD, reconcilers).

## Authentication & Identity

The current MVP uses header-based actor identification to record the `actor` in audit trails. This will be expanded in future milestones to enforce strict JWT-based or token-based authorization.

- **Header**: `X-Actor`
- **Default (if omitted)**: `admin-api`
- **Required**: For all mutating (`POST`, `PATCH`, `DELETE`) operations.

## Base Routes

### `GET /health`
Returns the operational status of the control-plane API itself.

### `GET /metrics`
Exposes Prometheus-formatted metrics, including:
- `litellm_requests_total`
- `litellm_request_errors_total`
- `litellm_active_incidents`

## Inventory Registry (`/registry/*`)

Standard CRUD operations are available for all base entities: Nodes, Providers, Models, Accounts, Endpoints, Consumers, and Policy Profiles.

### `GET /registry/{resource}`
List all resources of a given type.

### `GET /registry/{resource}/{id}`
Get a specific resource.

### `POST /registry/{resource}`
Create a new resource. Requires a JSON payload matching the `*Create` Pydantic models.

### `PATCH /registry/{resource}/{id}`
Update mutable fields on an existing resource.

### `DELETE /registry/{resource}/{id}`
Delete a resource. (Fails if the resource is in use / referenced by active topologies).

**Resource paths**:
- `/registry/nodes`
- `/registry/providers`
- `/registry/models`
- `/registry/accounts`
- `/registry/endpoints`
- `/registry/consumers`
- `/registry/profiles`

## Virtual Keys & Mapping (`/registry/keys`)

Manages the mapping of internal Consumers to LiteLLM native virtual keys deployed to specific nodes.

### `GET /registry/keys`
List all tracked virtual keys.

### `GET /registry/keys/{consumer_id}/{node_id}`
Get the virtual key details for a specific consumer on a specific node.

### `POST /registry/keys`
Create a new virtual key mapping.

### `DELETE /registry/keys/{consumer_id}/{node_id}`
Delete a virtual key mapping.

## Rollout & Drift (`/rollout/*`)

Manages configuration generation and deployment to LiteLLM nodes.

### `POST /rollout/apply`
- **Body**: `{"node_id": "string", "timeout_sec": float}`
- **Action**: Orchestrates a deployment (generate config, validate, canary, deploy).

### `POST /rollout/reconcile`
- **Body**: `{"node_id": "string", "timeout_sec": float}`
- **Action**: Detects config and virtual-key drift and automatically corrects the node's state.

## Health & Events (`/events/*`)

Endpoints for ingesting runtime callbacks from LiteLLM and modifying account states.

### `POST /events/callback`
- **Body**: Runtime execution logs or callback payloads.
- **Action**: Ingests success/failure signals to affect account/endpoint state machines.

### `POST /events/override`
- **Body**: `{"account_id": "string", "action": "disable|enable"}`
- **Action**: Manually overrides the health state machine for a specific account.

### `GET /timeline`
- **Query Params**: `?limit=50`
- **Action**: Returns a chronologically unified timeline of Audit Logs and Health Incidents for operator debugging.
