"""Unit tests for API routes and FastAPI app."""

from fastapi.testclient import TestClient

from gitpilot.api import routes
from gitpilot.github import MockGitHubClient
from gitpilot.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_get_graph_endpoint():
    resp = client.get("/api/v1/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "mermaid" in data
    assert "graph TD" in data["mermaid"]


def test_create_run_and_get():
    payload = {
        "repository_url": "https://github.com/demo/calculator",
        "issue_number": 1,
        "dry_run": True,
    }
    resp = client.post("/api/v1/runs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    run_id = data["run_id"]

    # Fetch run
    get_resp = client.get(f"/api/v1/runs/{run_id}")
    assert get_resp.status_code == 200
    run_data = get_resp.json()
    assert run_data["run_id"] == run_id
    assert run_data["repository_url"] == payload["repository_url"]


def test_issue_preview_mock(monkeypatch):
    monkeypatch.setattr(routes, "GitHubClient", lambda token="": MockGitHubClient())
    payload = {
        "repository_url": "https://github.com/demo/calculator",
        "issue_number": 1,
    }
    resp = client.post("/api/v1/github/issue/preview", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["number"] == 1
    assert "Calculator divide()" in data["title"]


def test_rejects_non_github_repository_url():
    from gitpilot.github import GitHubClient

    try:
        GitHubClient.parse_repo_url("https://example.com/owner/repo")
    except ValueError:
        pass
    else:
        raise AssertionError("Non-GitHub URL should have been rejected")
