from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

class NodeBase(BaseModel):
    id: str = Field(..., description="Unique node identifier")
    name: str
    host: str
    port: int
    region: str
    role: str = Field(..., description="e.g. proxy, exit, local-inference")
    status: Literal["active", "inactive", "degraded"] = "active"

class NodeCreate(NodeBase):
    pass

class NodeUpdate(BaseModel):
    """PATCH body for updating mutable node fields."""
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    region: Optional[str] = None
    role: Optional[str] = None
    status: Optional[Literal["active", "inactive", "degraded"]] = None

class Node(NodeBase):
    model_config = {"from_attributes": True}

class ProviderBase(BaseModel):
    id: str = Field(..., description="Unique provider identifier, e.g. openai")
    name: str
    type: str = Field(..., description="e.g. openai, anthropic, azure, ollama, nim")

class ProviderCreate(ProviderBase):
    pass

class ProviderUpdate(BaseModel):
    """PATCH body for updating mutable provider fields."""
    name: Optional[str] = None
    type: Optional[str] = None

class Provider(ProviderBase):
    model_config = {"from_attributes": True}

class ModelBase(BaseModel):
    id: str = Field(..., description="Unique model identifier, e.g. gemini-flash")
    name: str = Field(..., description="Upstream model name, e.g. gemini-2.5-flash")
    logical_group: str = Field(..., description="Logical grouping, e.g. general-chat")
    capability_chat: bool = True
    capability_stream: bool = True
    capability_tools: bool = True
    capability_embeddings: bool = False

class ModelCreate(ModelBase):
    pass

class ModelUpdate(BaseModel):
    """PATCH body for updating mutable model fields."""
    name: Optional[str] = None
    logical_group: Optional[str] = None
    capability_chat: Optional[bool] = None
    capability_stream: Optional[bool] = None
    capability_tools: Optional[bool] = None
    capability_embeddings: Optional[bool] = None

class Model(ModelBase):
    model_config = {"from_attributes": True}

class AccountBase(BaseModel):
    id: str = Field(..., description="Unique account identifier")
    name: str
    provider_id: str
    secret_ref: str = Field(..., description="Doppler secret reference, e.g. doppler://PROJECT/CONFIG/SECRET")
    status: Literal["active", "inactive", "cooldown", "disabled", "degraded", "probe", "recovered"] = "active"
    cooldown_until: Optional[str] = Field(None, description="ISO-8601 timestamp for cooldown end")
    failure_count: int = Field(default=0, description="Consecutive failure count")

    @field_validator("secret_ref")
    @classmethod
    def validate_secret_ref(cls, v: str) -> str:
        if not v.startswith("doppler://"):
            raise ValueError("secret_ref must start with 'doppler://'")
        return v

class AccountCreate(AccountBase):
    pass

class Account(AccountBase):
    model_config = {"from_attributes": True}

class EndpointBase(BaseModel):
    id: str = Field(..., description="Unique endpoint identifier")
    node_id: str
    account_id: str
    model_id: str
    priority: int = Field(default=1, description="Primary (1) vs Fallback (2+)")
    weight: int = Field(default=100, description="Load balancing weight")
    status: Literal["active", "degraded", "cooldown", "disabled", "probe", "recovered"] = "active"
    manual_override: Literal["none", "force-active", "force-disabled"] = "none"
    cooldown_until: Optional[str] = Field(None, description="ISO-8601 timestamp for cooldown end")
    failure_count: int = Field(default=0, description="Consecutive failure count")

class EndpointCreate(EndpointBase):
    pass

class Endpoint(EndpointBase):
    model_config = {"from_attributes": True}

class ConsumerBase(BaseModel):
    id: str = Field(..., description="Unique consumer identifier, e.g. coding-agent")
    name: str
    max_budget: Optional[float] = Field(None, description="Max budget allowance")
    rate_limit_rpm: Optional[int] = Field(None, description="Requests per minute limit")
    rate_limit_tpm: Optional[int] = Field(None, description="Tokens per minute limit")
    status: Literal["active", "disabled"] = "active"
    profile_id: Optional[str] = Field(None, description="Associated policy profile ID")

class ConsumerCreate(ConsumerBase):
    pass

class ConsumerUpdate(BaseModel):
    name: Optional[str] = None
    max_budget: Optional[float] = None
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None
    status: Optional[Literal["active", "disabled"]] = None
    profile_id: Optional[str] = None

class Consumer(ConsumerBase):
    model_config = {"from_attributes": True}

class ConsumerKeyBase(BaseModel):
    consumer_id: str
    node_id: str
    virtual_key: str
    status: Literal["active", "pending-sync", "disabled", "error"] = "pending-sync"

class ConsumerKeyCreate(ConsumerKeyBase):
    pass

class ConsumerKey(ConsumerKeyBase):
    model_config = {"from_attributes": True}

# --- Policy Profile Models ---

class PolicyProfileBase(BaseModel):
    id: str = Field(..., description="Unique profile identifier, e.g. coding, general-chat")
    name: str
    allowed_model_groups: str = Field(..., description="JSON string list of allowed model groups, e.g. ['premium', 'general']")
    description: Optional[str] = None

    @field_validator("allowed_model_groups")
    @classmethod
    def validate_allowed_model_groups(cls, v: str) -> str:
        import json
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, list):
                raise ValueError("allowed_model_groups must parse as a JSON list")
            for item in parsed:
                if not isinstance(item, str):
                    raise ValueError("All elements in allowed_model_groups list must be strings")
        except json.JSONDecodeError:
            raise ValueError("allowed_model_groups must be a valid JSON string")
        return v

class PolicyProfileCreate(PolicyProfileBase):
    pass

class PolicyProfileUpdate(BaseModel):
    name: Optional[str] = None
    allowed_model_groups: Optional[str] = None
    description: Optional[str] = None

    @field_validator("allowed_model_groups")
    @classmethod
    def validate_allowed_model_groups(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import json
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, list):
                raise ValueError("allowed_model_groups must parse as a JSON list")
        except json.JSONDecodeError:
            raise ValueError("allowed_model_groups must be a valid JSON string")
        return v

class PolicyProfile(PolicyProfileBase):
    model_config = {"from_attributes": True}

# --- Rollout Models ---

class RolloutBase(BaseModel):
    id: str = Field(..., description="Unique rollout identifier")
    node_id: str
    config_version: str
    status: Literal["pending", "applying", "success", "failed", "rolled_back"]
    config_content: str
    error_message: Optional[str] = None
    timestamp: Optional[str] = None

class Rollout(RolloutBase):
    model_config = {"from_attributes": True}


