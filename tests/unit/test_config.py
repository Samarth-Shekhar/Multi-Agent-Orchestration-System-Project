from pathlib import Path

from gitpilot.config import PROJECT_ROOT, Settings


def test_default_workspace_is_project_scoped(monkeypatch):
    monkeypatch.delenv("WORKSPACE_DIR", raising=False)
    settings = Settings(_env_file=None)
    assert settings.workspace_dir == PROJECT_ROOT / "workspaces"
    assert settings.workspace_dir.is_absolute()


def test_env_file_is_independent_of_current_directory():
    env_file = Path(Settings.model_config["env_file"])
    assert env_file == PROJECT_ROOT / ".env"
    assert env_file.is_absolute()
