"""Ollama local LLM provider."""

from __future__ import annotations

import httpx

from gitpilot.llm.base import BaseLLMProvider, LLMResponse


class OllamaProvider(BaseLLMProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url.rstrip("/")

    def name(self) -> str:
        return f"ollama:{self._model}"

    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": False,
        }
        resp = httpx.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(content=data.get("response", ""), model=self._model)
