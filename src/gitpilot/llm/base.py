"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict | None = None


class BaseLLMProvider(ABC):
    """Interface for all LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    @abstractmethod
    def name(self) -> str:
        ...
