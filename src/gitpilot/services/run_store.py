"""In-memory run store with pluggable persistence interface."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
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
    """Thread-safe in-memory run store."""

    def __init__(self):
        self._runs: dict[str, WorkflowRun] = {}
        self._lock = Lock()

    def create(self, repo_url: str, issue_number: int, dry_run: bool) -> WorkflowRun:
        run = WorkflowRun(
            run_id=str(uuid.uuid4())[:8],
            repository_url=repo_url,
            issue_number=issue_number,
            dry_run=dry_run,
        )
        with self._lock:
            self._runs[run.run_id] = run
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

    def add_event(self, run_id: str, event: dict) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run:
                run.events.append({"timestamp": time.time(), **event})

    def list_runs(self, limit: int = 20) -> list[WorkflowRun]:
        with self._lock:
            runs = sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)
            return runs[:limit]
