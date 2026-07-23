# Data Model Specification

This document defines the core entities and state objects that govern `litellm-control-plane`. These models act as the single source of truth for the system's runtime policy, secrets scoping, routing, and inventory tracking.

## Entities

### Node
Represents a physical or virtual machine running a proxy, exit, or inference workload.
- **id**: Unique node identifier
- **name**: Human-readable name
- **host**: IP address or hostname
- **port**: Service port
- **region**: Geographical or logical region (e.g., `us`, `kr`)
- **role**: Role of the node (`proxy`, `exit`, `local-inference`)
- **status**: Current state (`active`, `inactive`, `degraded`)

### Provider
Represents an upstream API or LLM supplier (independent of a specific credential).
- **id**: Unique identifier (e.g., `openai`)
- **name**: Display name
- **type**: Provider engine type (e.g., `openai`, `anthropic`, `ollama`, `nim`)

### Model
Represents an upstream LLM, normalizing capability flags for policy-based routing.
- **id**: Unique identifier (e.g., `gemini-flash`)
- **name**: Actual upstream model string (e.g., `gemini-2.5-flash`)
- **logical_group**: Group mapping (e.g., `general-chat`, `premium`)
- **capability_chat**: Boolean, whether it supports chat completions
- **capability_stream**: Boolean, whether it supports streaming
- **capability_tools**: Boolean, whether it supports function/tool calling
- **capability_embeddings**: Boolean, whether it supports embeddings

### Account
Represents a distinct set of credentials for a Provider. Accounts track failure counts and cooldown states.
- **id**: Unique account identifier
- **provider_id**: Reference to a Provider
- **secret_ref**: Doppler secret reference URI (must match format `doppler://PROJECT/CONFIG/SECRET`)
- **status**: Current state (`active`, `inactive`, `cooldown`, `disabled`, `degraded`, `probe`, `recovered`)
- **cooldown_until**: ISO-8601 timestamp representing the end of a penalty period
- **failure_count**: Consecutive request failures observed

### Endpoint
Concrete routable target linking a Model, an Account, and a Node.
- **id**: Unique identifier
- **node_id**: Reference to Node
- **account_id**: Reference to Account
- **model_id**: Reference to Model
- **priority**: Primary (1) vs Fallback (2+) selection priority
- **weight**: Load balancing weight
- **status**: Operational status (`active`, `degraded`, `cooldown`, `disabled`, `probe`, `recovered`)
- **manual_override**: Override setting (`none`, `force-active`, `force-disabled`)
- **cooldown_until**: Expiration of penalty period
- **failure_count**: Tracking consecutive failures mapped to this endpoint

### Consumer
Internal or external client permitted to access the control plane's managed LiteLLM nodes.
- **id**: Unique consumer identifier (e.g., `coding-agent`)
- **name**: Display name
- **max_budget**: Max financial budget allowed
- **rate_limit_rpm**: Requests per minute limit
- **rate_limit_tpm**: Tokens per minute limit
- **status**: Lifecycle state (`active`, `disabled`)
- **profile_id**: Reference to a Policy Profile governing routing

### ConsumerKey
Represents a generated LiteLLM virtual key associated with a Consumer on a specific Node.
- **consumer_id**: Reference to Consumer
- **node_id**: Reference to Node
- **virtual_key**: The actual generated key string
- **status**: Sync state (`active`, `pending-sync`, `disabled`, `error`)

### PolicyProfile
Bundled rules determining model eligibility for Consumers.
- **id**: Unique identifier
- **name**: Display name
- **allowed_model_groups**: JSON list of allowed model groups
- **description**: Documentation

### Rollout
Record of a configuration application attempt.
- **id**: Unique rollout identifier
- **node_id**: Target node
- **config_version**: Version of the generated configuration
- **status**: Execution state (`pending`, `applying`, `success`, `failed`, `rolled_back`)
- **config_content**: The raw LiteLLM YAML config generated
- **error_message**: Details if failed
- **timestamp**: ISO-8601 creation time

## State Modeling

* **Desired State**: The attributes defined in Node, Provider, Model, Account, Endpoint, and Consumer records representing the intended routing topology.
* **Applied State**: The YAML config successfully synchronized and applied to a Node via a `Rollout`, and the `ConsumerKey` virtual keys successfully injected into that Node's proxy.

* **Incident & CooldownState**: Driven by the `Account` and `Endpoint`'s `status`, `cooldown_until`, and `failure_count` fields. These are mutated by the Health Manager in response to 429s, 5xxs, and timeout events.
