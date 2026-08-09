"""Reviewer Agent — reviews generated diff for quality and correctness."""

from __future__ import annotations

import json
import logging

from gitpilot.errors import describe_error
from gitpilot.security import sanitize_for_prompt
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)

REVIEWER_SYSTEM = """You are a code review agent. Review the diff for:
- Issue alignment (does it fix what was reported?)
- Correctness
- Unnecessary changes
- Security risks
- Missing tests
- Backwards compatibility

Return JSON with:
- approved: true/false
- issues: list of issue strings
- summary: review summary

The reviewer MUST NOT modify code directly."""


def reviewer(state: AgentState, *, llm, **kwargs) -> dict:
    """Review generated changes."""
    log = state.get("execution_log", [])
    log.append("reviewer: starting")

    issue = state.get("issue", {})
    plan = state.get("plan", {})
    patch = state.get("patch", "")
    test_results = state.get("test_results", {})

    prompt = (
        f"Issue: {sanitize_for_prompt(issue.get('title', ''))}\n"
        f"Plan summary: {plan.get('summary', '')}\n\n"
        f"Changes:\n{sanitize_for_prompt(patch, max_length=5000)}\n\n"
        f"Test results: passed={test_results.get('passed', False)}\n\n"
        "Review these changes and return JSON with approved, issues, and summary."
    )

    try:
        response = llm.generate(prompt, system=REVIEWER_SYSTEM)
        review = _parse_review(response.content)

        log.append(f"reviewer: {'APPROVED' if review.get('approved') else 'CHANGES REQUESTED'}")
        if review.get("issues"):
            log.append(f"reviewer: {len(review['issues'])} issues found")

        return {
            "review_feedback": review,
            "execution_log": log,
        }
    except Exception as e:
        message = describe_error(e, "OpenAI")
        logger.error("Reviewer failed: %s", message)
        log.append(f"reviewer: failed - {message}")
        return {
            "status": "failed",
            "review_feedback": {
                "approved": False,
                "issues": [message],
                "summary": "Review could not be completed",
            },
            "errors": state.get("errors", []) + [message],
            "execution_log": log,
        }


def _parse_review(content: str) -> dict:
    """Extract review JSON from response."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        content = "\n".join(lines)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # If LLM didn't return valid JSON, interpret text
        approved = "approved" in content.lower() and "not approved" not in content.lower()
        return {
            "approved": approved,
            "issues": [] if approved else ["Review response was not structured"],
            "summary": content[:500],
        }
