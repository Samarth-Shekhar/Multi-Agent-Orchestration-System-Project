"""LLM provider factory."""

from __future__ import annotations

from gitpilot.llm.base import BaseLLMProvider, LLMResponse
from gitpilot.llm.mock import MockLLMProvider
from gitpilot.llm.ollama import OllamaProvider
from gitpilot.llm.openai_compatible import OpenAICompatibleProvider


def create_llm_provider(
    provider: str = "mock",
    model: str = "mock-model",
    ollama_base_url: str = "http://localhost:11434",
    openai_api_key: str = "",
    openai_base_url: str = "https://api.openai.com/v1",
    timeout_seconds: float = 600.0,
) -> BaseLLMProvider:
    """Create an LLM provider from configuration."""
    match provider:
        case "mock":
            return MockLLMProvider()
        case "ollama":
            return OllamaProvider(
                model=model, base_url=ollama_base_url, timeout_seconds=timeout_seconds
            )
        case "openai":
            if not openai_api_key or openai_api_key == "replace_with_your_openai_api_key":
                raise ValueError(
                    "OPENAI_API_KEY is not configured. Add your real key to .env "
                    "(not .env.example) and restart GitPilot."
                )
            return OpenAICompatibleProvider(
                model=model,
                api_key=openai_api_key,
                base_url=openai_base_url,
                timeout_seconds=timeout_seconds,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {provider}")


__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "MockLLMProvider",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "create_llm_provider",
]
