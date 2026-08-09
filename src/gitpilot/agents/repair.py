"""Repair Agent — fixes code based on test failures or review feedback."""

from __future__ import annotations

import logging

from gitpilot.errors import describe_error
from gitpilot.security import sanitize_for_prompt
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)

REPAIR_SYSTEM = """You are a repair agent. Fix the code based on test failures or review feedback.
Output only the corrected code. Do not explain the changes extensively."""


def repair_agent(state: AgentState, *, llm, **kwargs) -> dict:
    """Attempt to repair code based on feedback."""
    log = state.get("execution_log", [])
    attempt = state.get("attempt_count", 0)
    log.append(f"repair_agent: starting repair attempt {attempt}")

    patch = state.get("patch", "")
    test_results = state.get("test_results", {})
    review = state.get("review_feedback", {})
    plan = state.get("plan", {})

    # Build feedback context
    feedback_parts = []
    if test_results and not test_results.get("passed", True):
        feedback_parts.append(f"Test failure:\n{test_results.get('stderr', '')}")
        feedback_parts.append(f"Test stdout:\n{test_results.get('stdout', '')}")
    if review and review.get("issues"):
        feedback_parts.append("Review issues:\n" + "\n".join(review["issues"]))

    feedback = "\n\n".join(feedback_parts)

    prompt = (
        f"Plan:\n{sanitize_for_prompt(str(plan), max_length=2000)}\n\n"
        f"Current code:\n{sanitize_for_prompt(patch, max_length=4000)}\n\n"
        f"Feedback:\n{sanitize_for_prompt(feedback, max_length=3000)}\n\n"
        "Fix the code to address the feedback. Write the complete corrected code."
    )

    try:
        response = llm.generate(prompt, system=REPAIR_SYSTEM)
        repaired = response.content.strip()

        repair_history = state.get("repair_history", [])
        repair_history.append(f"Attempt {attempt}: {feedback[:200]}")

        log.append(f"repair_agent: generated repair ({len(repaired)} chars)")

        return {
            "patch": repaired,
            "repair_history": repair_history,
            "execution_log": log,
        }
    except Exception as e:
        message = describe_error(e, "OpenAI")
        logger.error("Repair agent failed: %s", message)
        log.append(f"repair_agent: failed - {message}")
        return {
            "status": "failed",
            "errors": state.get("errors", []) + [message],
            "execution_log": log,
        }
