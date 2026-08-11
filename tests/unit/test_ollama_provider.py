import json

import httpx
import respx

from gitpilot.llm.ollama import OllamaProvider


@respx.mock
def test_planner_gets_larger_json_generation_limit():
    route = respx.post("http://localhost:11434/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "{}", "done": True})
    )
    provider = OllamaProvider("test", cache_enabled=False)

    provider.generate("plan", system="You are a software planning agent. Return JSON.")

    payload = json.loads(route.calls[0].request.content)
    assert payload["options"]["num_predict"] == 1024
    assert payload["format"] == "json"


@respx.mock
def test_retries_once_when_ollama_truncates_output():
    route = respx.post("http://localhost:11434/api/generate").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"response": '{"summary":"cut', "done_reason": "length"},
            ),
            httpx.Response(200, json={"response": '{"summary":"complete"}'}),
        ]
    )
    provider = OllamaProvider("test", cache_enabled=False)

    response = provider.generate(
        "retry plan", system="You are a software planning agent. Return JSON."
    )

    assert response.content == '{"summary":"complete"}'
    assert len(route.calls) == 2
    retry_payload = json.loads(route.calls[1].request.content)
    assert retry_payload["options"]["num_predict"] == 2048
