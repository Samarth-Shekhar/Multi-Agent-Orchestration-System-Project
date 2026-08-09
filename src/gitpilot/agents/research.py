"""Research Agent — investigates additional code context for complex issues."""

from __future__ import annotations

import logging

from gitpilot.errors import describe_error
from gitpilot.security import sanitize_for_prompt
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)

RESEARCH_SYSTEM = """You are a code research agent. Investigate the referenced files, APIs,
and types to provide additional context needed for implementation.
Return concise, actionable research notes."""


def research_agent(state: AgentState, *, llm, **kwargs) -> dict:
    """Investigate additional context for complex issues."""
    log = state.get("execution_log", [])
    log.append("research_agent: starting")

    plan = state.get("plan", {})
    code_ctx = state.get("code_context", "")

    prompt = (
        f"Plan:\n{sanitize_for_prompt(str(plan), max_length=3000)}\n\n"
        f"Current code context:\n{sanitize_for_prompt(code_ctx, max_length=5000)}\n\n"
        "Investigate the referenced APIs, types, and dependencies. "
        "Return concise research notes to help with implementation."
    )

    try:
        response = llm.generate(prompt, system=RESEARCH_SYSTEM)
        notes = response.content.strip()
        log.append(f"research_agent: completed ({len(notes)} chars)")

        return {
            "research_notes": notes,
            "execution_log": log,
        }
    except Exception as e:
        message = describe_error(e, "OpenAI")
        logger.error("Research agent failed: %s", message)
        log.append(f"research_agent: failed - {message}")
        return {
            "status": "failed",
            "research_notes": "",
            "errors": state.get("errors", []) + [message],
            "execution_log": log,
        }
