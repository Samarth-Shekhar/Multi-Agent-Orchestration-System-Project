"""Typed shared state for the LangGraph workflow."""

from __future__ import annotations

from typing import TypedDict


class Issue(TypedDict, total=False):
    number: int
    title: str
    body: str
    labels: list[str]
    url: str


class Plan(TypedDict, total=False):
    summary: str
    root_cause: str
    files_to_modify: list[str]
    files_to_add: list[str]
    implementation_steps: list[str]
    test_strategy: list[str]
    risk_level: str       # low | medium | high
    complexity: str       # simple | complex


class TestResults(TypedDict, total=False):
    passed: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    framework: str
    command: str


class ReviewResult(TypedDict, total=False):
    approved: bool
    issues: list[str]
    summary: str


class AgentState(TypedDict, total=False):
    """Shared state flowing through the LangGraph workflow."""
    # Input
    issue: Issue
    repository_url: str
    repo_path: str
    default_branch: str

    # Code analysis
    code_context: str
    retrieved_files: list[str]
    file_tree: str

    # Planning
    plan: Plan
    complexity: str  # simple | complex

    # Research
    research_notes: str

    # Code generation
    patch: str
    changed_files: list[str]
    diff_summary: str

    # Testing
    tests: str
    test_files: list[str]
    test_results: TestResults

    # Review
    review_feedback: ReviewResult

    # Repair loop
    attempt_count: int
    max_attempts: int
    repair_history: list[str]

    # Output
    branch_name: str
    pr_url: str
    pr_body: str
    status: str  # pending | running | success | failed
    errors: list[str]
    execution_log: list[str]
