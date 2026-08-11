"""Ollama local LLM provider."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx

from gitpilot.llm.base import BaseLLMProvider, LLMResponse


class OllamaProvider(BaseLLMProvider):
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 600.0,
        cache_enabled: bool = True,
    ):
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._cache_enabled = cache_enabled
        self._cache_dir = Path(__file__).resolve().parents[3] / ".tools" / "llm-cache"

    def name(self) -> str:
        return f"ollama:{self._model}"

    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        cache_key = hashlib.sha256(
            f"{self._model}\0{system}\0{prompt}".encode()
        ).hexdigest()
        cache_file = self._cache_dir / f"{cache_key}.json"
        if self._cache_enabled and cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                return LLMResponse(content=cached["content"], model=self._model)
            except (OSError, ValueError, KeyError, TypeError):
                pass

        num_predict = self._generation_limit(system)
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"num_predict": num_predict},
        }
        if "json" in system.lower():
            payload["format"] = "json"
        data = self._request(payload)
        if data.get("done_reason") == "length":
            # Retry once with more output room instead of handing downstream
            # agents a predictably truncated JSON document or source file.
            payload["options"]["num_predict"] = min(num_predict * 2, 3072)
            data = self._request(payload)
        content = data.get("response", "")
        if self._cache_enabled:
            try:
                self._cache_dir.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps({"content": content}), encoding="utf-8")
            except OSError:
                pass
        return LLMResponse(content=content, model=self._model)

    def _request(self, payload: dict) -> dict:
        resp = httpx.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _generation_limit(system: str) -> int:
        lowered = system.lower()
        if "code implementation" in lowered or "repair" in lowered:
            return 1536
        if "test writing" in lowered:
            return 1024
        if "research" in lowered:
            return 768
        if "planning agent" in lowered:
            return 1024
        return 512
