"""OpenAI-compatible API provider."""

from __future__ import annotations

import httpx

from gitpilot.llm.base import BaseLLMProvider, LLMResponse


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(self, model: str, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def name(self) -> str:
        return f"openai:{self._model}"

    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        resp = httpx.post(
            f"{self._base_url}/responses",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "instructions": system,
                "input": prompt,
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("output_text", "")
        if not content:
            text_parts = []
            for output in data.get("output", []):
                for item in output.get("content", []):
                    if item.get("type") == "output_text" and item.get("text"):
                        text_parts.append(item["text"])
            content = "\n".join(text_parts)
        if not content:
            raise ValueError("OpenAI response did not contain text output")
        usage = data.get("usage")
        return LLMResponse(content=content, model=self._model, usage=usage)
