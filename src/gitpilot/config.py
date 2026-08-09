"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # LLM
    llm_provider: str = Field(default="mock", description="ollama | openai | mock")
    llm_model: str = Field(default="mock-model")
    ollama_base_url: str = Field(default="http://localhost:11434")
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="https://api.openai.com/v1")

    # GitHub
    github_token: str = Field(default="")

    # Workflow
    dry_run: bool = Field(default=True)
    max_repair_attempts: int = Field(default=3)

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    log_level: str = Field(default="info")

    # Paths
    workspace_dir: Path = Field(default=PROJECT_ROOT / "workspaces")

    model_config = {
        "env_file": PROJECT_ROOT / ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset cached settings (useful for testing)."""
    global _settings
    _settings = None
