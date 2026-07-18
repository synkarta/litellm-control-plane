# Provider Baseline Specification

To guarantee safety and prevent routing requests to unsupported or malfunctioning provider endpoints, every upstream provider configuration (OpenAI, Anthropic, Azure, Ollama, NIM, etc.) must undergo a Compatibility Baseline check before being made eligible in policy.

---

## 1. Onboarding Test Matrix

The test suite must validate the following capability dimensions:

| Capability | Test Scenario | Required Behavior |
|---|---|---|
| **Chat** | Standard non-streaming prompt completion | Return status 200, valid JSON schema structure matching OpenAI standard |
| **Streaming** | Streamed prompt completion (SSE) | Yield sequential chunks, terminate correctly, match token-usage data if requested |
| **Tool Calling** | Function/tool definition passed | Model returns structural tool calls, parses correctly without hallucination |
| **Embeddings** | Request vector embeddings for text | Return normalized float array, correct dimension length |
| **Error Mapping** | Force failures (429 Rate Limit, 401 Auth, 400 Bad Param) | LiteLLM translates upstream errors to standardized exceptions |

---

## 2. Health & Timeout Benchmarks

In addition to feature support, the baseline checks must record performance metrics to seed the registries:
*   **Time-to-First-Token (TTFT)**: For streaming endpoints, TTFT must be measured. If average TTFT > 3000ms under standard load, the endpoint is flagged as `degraded` in the registry.
*   **Connection Timeout**: Upstream connection must be established within 5000ms.
*   **Error Rate Tolerance**: Onboarding baseline requires at least 98% success rate over a 50-request warm-up run.

---

## 3. Upstream Error Handling and Code Classification

To verify that the Account State Machine can react properly to failures, the provider baseline checks must verify that LiteLLM maps errors to standard HTTP status codes:
*   **Rate Limits**: 429 Too Many Requests -> Must trigger transition to `cooldown` state.
*   **Authentication**: 401 Unauthorized / 403 Forbidden -> Must trigger transition to `disabled` state immediately.
*   **Upstream Downtime**: 502 Bad Gateway / 503 Service Unavailable / 504 Gateway Timeout -> Must trigger cooldown and subsequent retry checks.

---

## 4. Runbook: Executing the Baseline Suite

Before adding a new account or provider to production:
1.  Configure the provider with a temporary key inside a Doppler `tst` configuration.
2.  Run the provider baseline test command:
    ```bash
    pytest tests/provider_baseline/ --provider=<provider-name> --endpoint=<url>
    ```
3.  Check the test output and JSON capability report:
    *   If all tests pass, the provider/endpoint capability flags are set to `active`.
    *   If specific capabilities fail (e.g., streaming is unsupported), they are flagged as `disabled` for that endpoint, preventing policies requiring streaming from selecting it.
