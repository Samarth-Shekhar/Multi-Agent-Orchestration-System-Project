"""Test Writer Agent — generates appropriate tests based on the plan and conventions."""

from __future__ import annotations

import logging

from gitpilot.errors import describe_error
from gitpilot.security import sanitize_for_prompt
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)

TEST_WRITER_SYSTEM = """You are a test writing agent. Generate tests based on the implementation
plan and testing strategy. Follow the project's existing test conventions.
Output only test code. Use pytest unless the project uses a different framework."""


def test_writer(state: AgentState, *, llm, **kwargs) -> dict:
    """Generate tests for the code changes."""
    log = state.get("execution_log", [])
    log.append("test_writer: starting")

    plan = state.get("plan", {})
    patch = state.get("patch", "")
    code_ctx = state.get("code_context", "")

    prompt = (
        f"Plan:\n{sanitize_for_prompt(str(plan), max_length=2000)}\n\n"
        f"Implementation:\n{sanitize_for_prompt(patch, max_length=3000)}\n\n"
        f"Existing code:\n{sanitize_for_prompt(code_ctx, max_length=3000)}\n\n"
        "Generate test code following the test strategy."
    )

    try:
        response = llm.generate(prompt, system=TEST_WRITER_SYSTEM)
        test_code = response.content.strip()
        log.append(f"test_writer: generated {len(test_code)} chars of test code")

        return {
            "tests": test_code,
            "test_files": [f"test_{f}" for f in plan.get("files_to_modify", [])],
            "execution_log": log,
        }
    except Exception as e:
        message = describe_error(e, "OpenAI")
        logger.error("Test writer failed: %s", message)
        log.append(f"test_writer: failed - {message}")
        return {
            "status": "failed",
            "tests": "",
            "test_files": [],
            "errors": state.get("errors", []) + [message],
            "execution_log": log,
        }
