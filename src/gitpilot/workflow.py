"""LangGraph StateGraph workflow — the core orchestration engine.

Defines the multi-agent graph with conditional routing:
- Complexity-based routing (simple → code_writer, complex → research → code_writer)
- Test result routing (pass → reviewer, fail → repair loop)
- Review routing (approved → pr_opener, changes → repair)
- Bounded repair retries (max_attempts → safe failure)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import partial
from typing import Literal

from langgraph.graph import END, StateGraph

from gitpilot.agents import (
    code_reader,
    code_writer,
    issue_loader,
    planner,
    pr_opener,
    repair_agent,
    research_agent,
    reviewer,
    test_runner,
    test_writer,
)
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)


# ── Routing functions ──────────────────────────────────────────────


def route_after_agent(state: AgentState) -> Literal["continue", "__end__"]:
    """Stop immediately when an agent reports a fatal failure."""
    return "__end__" if state.get("status") == "failed" else "continue"


def route_by_complexity(state: AgentState) -> Literal["research_agent", "code_writer", "__end__"]:
    """Route based on plan complexity: complex issues go through research first."""
    if state.get("status") == "failed":
        return "__end__"
    logger.info("Routing: planner → research_agent")
    return "research_agent"


def route_after_tests(state: AgentState) -> Literal["reviewer", "repair_agent", "__end__"]:
    """Route based on test results and retry budget."""
    if state.get("status") == "failed":
        return "__end__"
    test_results = state.get("test_results", {})
    attempt = state.get("attempt_count", 0)
    max_attempts = state.get("max_attempts", 3)

    if test_results.get("passed", False):
        logger.info("Routing: tests passed → reviewer")
        return "reviewer"

    if attempt >= max_attempts:
        logger.warning("Routing: max attempts (%d) reached → END", max_attempts)
        return "__end__"

    logger.info("Routing: tests failed (attempt %d/%d) → repair_agent", attempt, max_attempts)
    return "repair_agent"


def route_after_review(state: AgentState) -> Literal["pr_opener", "repair_agent", "__end__"]:
    """Route based on review outcome."""
    if state.get("status") == "failed":
        return "__end__"
    review = state.get("review_feedback", {})
    if review.get("approved", False):
        logger.info("Routing: approved → pr_opener")
        return "pr_opener"
    logger.info("Routing: changes requested → repair_agent")
    return "repair_agent"


# ── Safe failure node ──────────────────────────────────────────────


def _safe_end(state: AgentState) -> dict:
    """Mark workflow as failed gracefully."""
    log = state.get("execution_log", [])
    log.append("workflow: ending with safe failure (max retries exceeded)")
    return {
        "status": "failed",
        "execution_log": log,
    }


# ── Graph builder ──────────────────────────────────────────────────


def build_workflow(
    *,
    llm,
    github_client,
    dry_run: bool = True,
    event_callback: Callable[[str, str], None] | None = None,
) -> StateGraph:
    """Build and compile the LangGraph StateGraph.

    Returns a compiled graph ready for invocation.
    """

    # Create node functions with injected dependencies
    def evented(name, function):
        if event_callback is None:
            return function

        def wrapped(state):
            event_callback(name, "running")
            result = function(state)
            status = "failed" if result.get("status") == "failed" else "completed"
            event_callback(name, status)
            return result

        return wrapped

    _issue_loader = evented("issue_loader", partial(issue_loader, github_client=github_client))
    _code_reader = evented("code_reader", partial(code_reader, llm=llm))
    _planner = evented("planner", partial(planner, llm=llm))
    _research = evented("research_agent", partial(research_agent, llm=llm))
    _code_writer = evented("code_writer", partial(code_writer, llm=llm))
    _test_writer = evented("test_writer", partial(test_writer, llm=llm))
    _test_runner = evented("test_runner", test_runner)
    _reviewer = evented("reviewer", partial(reviewer, llm=llm))
    _repair = evented("repair_agent", partial(repair_agent, llm=llm))
    _pr_opener = evented(
        "pr_opener", partial(pr_opener, github_client=github_client, dry_run=dry_run)
    )

    # Define the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("issue_loader", _issue_loader)
    graph.add_node("code_reader", _code_reader)
    graph.add_node("planner", _planner)
    graph.add_node("research_agent", _research)
    graph.add_node("code_writer", _code_writer)
    graph.add_node("test_writer", _test_writer)
    graph.add_node("test_runner", _test_runner)
    graph.add_node("reviewer", _reviewer)
    graph.add_node("repair_agent", _repair)
    graph.add_node("pr_opener", _pr_opener)

    # Entry point
    graph.set_entry_point("issue_loader")

    # Linear edges
    graph.add_conditional_edges(
        "issue_loader", route_after_agent, {"continue": "code_reader", "__end__": END}
    )
    graph.add_conditional_edges(
        "code_reader", route_after_agent, {"continue": "planner", "__end__": END}
    )

    # Conditional: complexity routing
    graph.add_conditional_edges(
        "planner",
        route_by_complexity,
        {
            "research_agent": "research_agent",
            "code_writer": "code_writer",
            "__end__": END,
        },
    )

    # Research → code_writer
    graph.add_conditional_edges(
        "research_agent", route_after_agent, {"continue": "code_writer", "__end__": END}
    )

    # Code writer → test writer → test runner
    graph.add_conditional_edges(
        "code_writer", route_after_agent, {"continue": "test_writer", "__end__": END}
    )
    graph.add_conditional_edges(
        "test_writer", route_after_agent, {"continue": "test_runner", "__end__": END}
    )

    # Conditional: test results
    graph.add_conditional_edges(
        "test_runner",
        route_after_tests,
        {
            "reviewer": "reviewer",
            "repair_agent": "repair_agent",
            "__end__": END,
        },
    )

    # Repair → test_runner (retry loop)
    graph.add_conditional_edges(
        "repair_agent", route_after_agent, {"continue": "test_runner", "__end__": END}
    )

    # Conditional: review outcome
    graph.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "pr_opener": "pr_opener",
            "repair_agent": "repair_agent",
            "__end__": END,
        },
    )

    # PR opener → END
    graph.add_edge("pr_opener", END)

    return graph.compile()


def run_workflow(
    *,
    repository_url: str,
    issue_number: int,
    llm,
    github_client,
    dry_run: bool = True,
    max_attempts: int = 3,
    repo_path: str = "",
    event_callback: Callable[[str, str], None] | None = None,
) -> AgentState:
    """Execute the full workflow and return final state."""
    start = time.time()

    compiled = build_workflow(
        llm=llm,
        github_client=github_client,
        dry_run=dry_run,
        event_callback=event_callback,
    )

    initial_state: AgentState = {
        "issue": {"number": issue_number},
        "repository_url": repository_url,
        "repo_path": repo_path,
        "default_branch": "main",
        "code_context": "",
        "retrieved_files": [],
        "file_tree": "",
        "plan": {},
        "complexity": "simple",
        "research_notes": "",
        "patch": "",
        "changed_files": [],
        "diff_summary": "",
        "tests": "",
        "test_files": [],
        "test_results": {},
        "review_feedback": {},
        "attempt_count": 0,
        "max_attempts": max_attempts,
        "repair_history": [],
        "branch_name": "",
        "pr_url": "",
        "pr_body": "",
        "status": "pending",
        "errors": [],
        "execution_log": ["workflow: initialized"],
    }

    logger.info("Starting workflow for %s#%d (dry_run=%s)", repository_url, issue_number, dry_run)

    try:
        result = compiled.invoke(initial_state)
        elapsed = time.time() - start

        result["execution_log"] = result.get("execution_log", [])
        result["execution_log"].append(f"workflow: completed in {elapsed:.2f}s")

        tests = result.get("test_results", {})
        if result.get("status") == "failed" or (tests and not tests.get("passed", False)):
            result["status"] = "failed"
        else:
            result["status"] = "success"

        logger.info("Workflow completed in %.2fs with status=%s", elapsed, result["status"])
        return result

    except Exception as e:
        elapsed = time.time() - start
        logger.error("Workflow crashed after %.2fs: %s", elapsed, e)
        initial_state["status"] = "failed"
        initial_state["errors"] = initial_state.get("errors", []) + [f"Workflow crash: {e}"]
        initial_state["execution_log"].append(f"workflow: crashed - {e}")
        return initial_state


def export_mermaid() -> str:
    """Export the workflow graph as a Mermaid diagram."""
    return """graph TD
    A[Issue Loader] --> B[Code Reader]
    B --> C[Planner]
    C -->|simple| E[Code Writer]
    C -->|complex| D[Research Agent]
    D --> E
    E --> F[Test Writer]
    F --> G[Test Runner]
    G -->|pass| H[Reviewer]
    G -->|fail & retries left| I[Repair Agent]
    G -->|fail & max retries| END_FAIL[Safe Failure END]
    I --> G
    H -->|approved| J[PR Opener]
    H -->|changes requested| I
    J --> END_OK[Success END]

    style A fill:#4A9EFF,color:#fff
    style B fill:#4A9EFF,color:#fff
    style C fill:#FF9F43,color:#fff
    style D fill:#A55EEA,color:#fff
    style E fill:#26DE81,color:#fff
    style F fill:#26DE81,color:#fff
    style G fill:#FD9644,color:#fff
    style H fill:#FC5C65,color:#fff
    style I fill:#FC5C65,color:#fff
    style J fill:#20BF6B,color:#fff
    style END_OK fill:#20BF6B,color:#fff
    style END_FAIL fill:#EB3B5A,color:#fff
"""
