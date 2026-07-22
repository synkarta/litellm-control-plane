from prometheus_client import Counter, Histogram, REGISTRY

def get_or_create_counter(name: str, documentation: str, labelnames: list[str]) -> Counter:
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return Counter(name, documentation, labelnames)

def get_or_create_histogram(name: str, documentation: str, labelnames: list[str]) -> Histogram:
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return Histogram(name, documentation, labelnames)

REQUESTS_TOTAL = get_or_create_counter(
    "litellm_requests_total",
    "Total requests processed by the LiteLLM nodes",
    ["node_id", "account_id", "endpoint_id", "status"]
)

REQUEST_LATENCY_SECONDS = get_or_create_histogram(
    "litellm_request_latency_seconds",
    "Request latency in seconds",
    ["node_id", "account_id", "endpoint_id"]
)

TOKENS_TOTAL = get_or_create_counter(
    "litellm_tokens_total",
    "Total tokens consumed",
    ["node_id", "account_id", "endpoint_id", "token_type"]
)

DRIFT_DETECTION_TOTAL = get_or_create_counter(
    "control_plane_drift_detected_total",
    "Total drift detections on LiteLLM nodes",
    ["node_id"]
)

HEALTH_EVENTS_TOTAL = get_or_create_counter(
    "control_plane_health_events_total",
    "Total health state transitions",
    ["entity_type", "entity_id", "state_from", "state_to"]
)
