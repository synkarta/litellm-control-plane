import os
import httpx
import pytest
from tests.provider_baseline.test_chat import should_skip, MODELS

@pytest.mark.parametrize("model_name", MODELS.keys())
def test_tool_calling(litellm_proxy_url, model_name):
    if should_skip(model_name):
        pytest.skip(f"Skipping {model_name}: {MODELS[model_name]['skip_reason']}")

    url = f"{litellm_proxy_url}/v1/chat/completions"
    
    # Define a simple weather tool
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"]
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "What's the weather like in Tokyo right now?"}],
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.0,
    }

    response = httpx.post(url, json=payload, timeout=20.0)
    assert response.status_code == 200, f"Failed: {response.text}"
    
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    message = data["choices"][0]["message"]
    
    # Assert that tool_calls exists in the response
    assert "tool_calls" in message, f"No tool calls returned for {model_name}. Response: {data}"
    tool_calls = message["tool_calls"]
    assert len(tool_calls) > 0
    assert tool_calls[0]["function"]["name"] == "get_current_weather"
    print(f"\nModel {model_name} successfully executed tool call: {tool_calls[0]['function']}")
