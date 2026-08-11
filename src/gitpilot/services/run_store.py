"""In-memory run store with pluggable persistence interface."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Protocol

from gitpilot.state import AgentState


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class WorkflowRun:
    run_id: str
    repository_url: str
    issue_number: int
    dry_run: bool
    status: RunStatus = RunStatus.PENDING
    state: AgentState | None = None
    events: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None


class RunStoreProtocol(Protocol):
    """Interface for run persistence — enables swapping in-memory for DB later."""

    def create(self, repo_url: str, issue_number: int, dry_run: bool) -> WorkflowRun: ...
    def get(self, run_id: str) -> WorkflowRun | None: ...
    def update(self, run_id: str, **kwargs) -> None: ...
    def list_runs(self, limit: int = 20) -> list[WorkflowRun]: ...


class InMemoryRunStore:
    """Thread-safe run store persisted to a small project-local JSON file."""

    def __init__(self, persistence_path: Path | None = None):
        self._runs: dict[str, WorkflowRun] = {}
        self._lock = Lock()
        self._persistence_path = persistence_path
        self._load()

    def _load(self) -> None:
        if not self._persistence_path or not self._persistence_path.exists():
            return
        try:
            payload = json.loads(self._persistence_path.read_text(encoding="utf-8"))
            for item in payload:
                item["status"] = RunStatus(item["status"])
                run = WorkflowRun(**item)
                self._runs[run.run_id] = run
        except (OSError, ValueError, TypeError):
            self._runs = {}

    def _save(self) -> None:
        if not self._persistence_path:
            return
        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                **run.__dict__,
                "status": run.status.value,
            }
            for run in self._runs.values()
        ]
        temporary = self._persistence_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self._persistence_path)

    def create(self, repo_url: str, issue_number: int, dry_run: bool) -> WorkflowRun:
        run = WorkflowRun(
            run_id=str(uuid.uuid4())[:8],
            repository_url=repo_url,
            issue_number=issue_number,
            dry_run=dry_run,
        )
        with self._lock:
            self._runs[run.run_id] = run
            self._save()
        return run

    def get(self, run_id: str) -> WorkflowRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def update(self, run_id: str, **kwargs) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run:
                for k, v in kwargs.items():
                    setattr(run, k, v)
                if kwargs.get("status") in {RunStatus.SUCCESS, RunStatus.FAILED}:
                    run.completed_at = time.time()
                self._save()

    def add_event(self, run_id: str, event: dict) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run:
                run.events.append({"timestamp": time.time(), **event})
                self._save()

    def list_runs(self, limit: int = 20) -> list[WorkflowRun]:
        with self._lock:
            runs = sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)
            return runs[:limit]
