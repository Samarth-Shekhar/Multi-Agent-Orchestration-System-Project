"""Unit tests for LangGraph StateGraph workflow routing and compilation."""

from gitpilot.github.client import MockGitHubClient
from gitpilot.llm.mock import MockLLMProvider
from gitpilot.workflow import (
    build_workflow,
    export_mermaid,
    route_after_agent,
    route_after_review,
    route_after_tests,
    route_by_complexity,
    run_workflow,
)


def test_build_workflow_compilation():
    llm = MockLLMProvider()
    gh = MockGitHubClient()
    compiled = build_workflow(llm=llm, github_client=gh, dry_run=True)
    assert compiled is not None


def test_route_by_complexity_simple():
    state = {"complexity": "simple"}
    assert route_by_complexity(state) == "research_agent"


def test_fatal_agent_failure_stops_pipeline():
    state = {"status": "failed", "errors": ["service unavailable"]}
    assert route_after_agent(state) == "__end__"
    assert route_by_complexity(state) == "__end__"
    assert route_after_tests(state) == "__end__"
    assert route_after_review(state) == "__end__"


def test_route_by_complexity_complex():
    state = {"complexity": "complex"}
    assert route_by_complexity(state) == "research_agent"


def test_route_after_tests_passed():
    state = {"test_results": {"passed": True}, "attempt_count": 1, "max_attempts": 3}
    assert route_after_tests(state) == "reviewer"


def test_route_after_tests_failed_retry_available():
    state = {"test_results": {"passed": False}, "attempt_count": 1, "max_attempts": 3}
    assert route_after_tests(state) == "repair_agent"


def test_route_after_tests_failed_max_attempts():
    state = {"test_results": {"passed": False}, "attempt_count": 3, "max_attempts": 3}
    assert route_after_tests(state) == "__end__"


def test_route_after_review_approved():
    state = {"review_feedback": {"approved": True}}
    assert route_after_review(state) == "pr_opener"


def test_route_after_review_changes_requested():
    state = {"review_feedback": {"approved": False}}
    assert route_after_review(state) == "repair_agent"


def test_export_mermaid():
    mermaid = export_mermaid()
    assert "graph TD" in mermaid
    assert "Issue Loader" in mermaid
    assert "PR Opener" in mermaid


def test_run_workflow_end_to_end():
    llm = MockLLMProvider()
    gh = MockGitHubClient()
    result = run_workflow(
        repository_url="https://github.com/demo/calculator",
        issue_number=1,
        llm=llm,
        github_client=gh,
        dry_run=True,
    )

    assert result["status"] == "success"
    assert result["issue"]["number"] == 1
    assert "branch_name" in result
    assert "pr_url" in result
    assert len(result["execution_log"]) > 5
