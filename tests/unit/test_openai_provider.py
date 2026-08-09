import httpx
import pytest
import respx

from gitpilot.errors import describe_error
from gitpilot.llm import create_llm_provider
from gitpilot.llm.openai_compatible import OpenAICompatibleProvider


def test_placeholder_api_key_is_rejected():
    with pytest.raises(ValueError, match=r"Add your real key to .env"):
        create_llm_provider(
            provider="openai",
            model="test-model",
            openai_api_key="replace_with_your_openai_api_key",
        )


def test_deleted_github_issue_has_actionable_error():
    request = httpx.Request("GET", "https://api.github.com/repos/example/repo/issues/1")
    response = httpx.Response(410, request=request)
    error = httpx.HTTPStatusError("gone", request=request, response=response)
    assert "deleted" in describe_error(error, "GitHub").lower()


@respx.mock
def test_openai_provider_uses_responses_api():
    route = respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "repository-specific result"}
                        ]
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 3},
            },
        )
    )
    provider = OpenAICompatibleProvider(
        model="test-model", api_key="sk-test", base_url="https://api.openai.com/v1"
    )

    response = provider.generate("Fix issue 12", system="Return JSON")

    assert response.content == "repository-specific result"
    assert route.called
    payload = route.calls[0].request.content.decode()
    assert '"input":"Fix issue 12"' in payload
    assert '"instructions":"Return JSON"' in payload
