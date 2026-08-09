"""FastAPI API routes."""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gitpilot.config import get_settings
from gitpilot.github import GitHubClient
from gitpilot.llm import create_llm_provider
from gitpilot.services.run_store import InMemoryRunStore, RunStatus
from gitpilot.workflow import export_mermaid, run_workflow

router = APIRouter()
run_store = InMemoryRunStore()
PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ── Request / Response models ──────────────────────────────────────


class RunRequest(BaseModel):
    repository_url: str = Field(..., description="GitHub repository URL")
    issue_number: int = Field(..., gt=0, description="Issue number")
    dry_run: bool = Field(default=True, description="If true, skip actual PR creation")


class RunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class RunDetail(BaseModel):
    run_id: str
    repository_url: str
    issue_number: int
    dry_run: bool
    status: str
    state: dict | None = None
    events: list[dict] = []


class IssuePreview(BaseModel):
    repository_url: str = Field(..., description="GitHub repository URL")
    issue_number: int = Field(..., gt=0)


class IssuePreviewResponse(BaseModel):
    number: int
    title: str
    body: str
    labels: list[str]


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@router.get("/api/v1/graph")
def get_graph():
    """Return the workflow graph as Mermaid."""
    return {"mermaid": export_mermaid()}


@router.post("/api/v1/runs", response_model=RunResponse)
def create_run(req: RunRequest):
    """Start a new workflow run."""
    run = run_store.create(req.repository_url, req.issue_number, req.dry_run)

    # Execute workflow in background thread
    thread = threading.Thread(
        target=_execute_run,
        args=(run.run_id, req.repository_url, req.issue_number, req.dry_run),
        daemon=True,
    )
    thread.start()

    return RunResponse(
        run_id=run.run_id,
        status=run.status.value,
        message="Workflow started",
    )


@router.get("/api/v1/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str):
    """Get run details."""
    run = run_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunDetail(
        run_id=run.run_id,
        repository_url=run.repository_url,
        issue_number=run.issue_number,
        dry_run=run.dry_run,
        status=run.status.value,
        state=run.state if run.state else None,
        events=run.events,
    )


@router.get("/api/v1/runs/{run_id}/events")
def get_run_events(run_id: str):
    """Get run events for live updates."""
    run = run_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "events": run.events, "status": run.status.value}


@router.post("/api/v1/github/issue/preview", response_model=IssuePreviewResponse)
def preview_issue(req: IssuePreview):
    """Preview a GitHub issue without running the workflow."""
    settings = get_settings()
    client = GitHubClient(settings.github_token)

    try:
        owner, repo = client.parse_repo_url(req.repository_url)
        issue = client.get_issue(owner, repo, req.issue_number)
        return IssuePreviewResponse(
            number=issue.number,
            title=issue.title,
            body=issue.body,
            labels=issue.labels,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        client.close()


# ── Background execution ──────────────────────────────────────────


def _execute_run(run_id: str, repo_url: str, issue_number: int, dry_run: bool):
    """Execute workflow in background."""
    settings = get_settings()
    run_store.update(run_id, status=RunStatus.RUNNING)
    run_store.add_event(run_id, {"node": "workflow", "status": "started"})

    try:
        llm = create_llm_provider(
            provider=settings.llm_provider,
            model=settings.llm_model,
            ollama_base_url=settings.ollama_base_url,
            openai_api_key=settings.openai_api_key,
            openai_base_url=settings.openai_base_url,
        )

        # Public repositories can be read without a token. Each workflow gets
        # its own clone so code context and tests always match the submitted URL.
        gh = GitHubClient(settings.github_token)
        owner, repo_name = gh.parse_repo_url(repo_url)
        repo_info = gh.get_repo(owner, repo_name)
        configured_workspace = Path(settings.workspace_dir)
        if not configured_workspace.is_absolute():
            configured_workspace = PROJECT_ROOT / configured_workspace
        workspace_root = configured_workspace.resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)
        repo_path = (workspace_root / run_id).resolve()
        if workspace_root not in repo_path.parents:
            raise ValueError("Invalid workspace path")
        run_store.add_event(
            run_id,
            {
                "node": "code_reader",
                "status": "running",
                "message": f"Cloning {owner}/{repo_name}",
            },
        )
        gh.download_repository(owner, repo_name, repo_info.default_branch, repo_path)

        result = run_workflow(
            repository_url=repo_url,
            issue_number=issue_number,
            llm=llm,
            github_client=gh,
            dry_run=dry_run,
            max_attempts=settings.max_repair_attempts,
            repo_path=str(repo_path),
        )

        # Update run store
        status = RunStatus.SUCCESS if result.get("status") == "success" else RunStatus.FAILED
        run_store.update(run_id, status=status, state=dict(result))

        # Add completion event
        for entry in result.get("execution_log", []):
            run_store.add_event(run_id, {"node": "log", "message": entry})

        run_store.add_event(run_id, {"node": "workflow", "status": status.value})

    except Exception as e:
        run_store.update(
            run_id,
            status=RunStatus.FAILED,
            state={
                "repository_url": repo_url,
                "issue": {"number": issue_number},
                "status": "failed",
                "errors": [str(e)],
                "execution_log": [f"workflow: failed - {e}"],
            },
        )
        run_store.add_event(run_id, {"node": "workflow", "status": "failed", "error": str(e)})
