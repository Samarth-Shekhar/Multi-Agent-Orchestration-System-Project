"""Planner Agent — creates structured implementation plan from issue + code context."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, field_validator

from gitpilot.errors import describe_error
from gitpilot.security import sanitize_for_prompt
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)


class PlanModel(BaseModel):
    """Validated plan output from the planner agent."""
    summary: str
    root_cause: str
    files_to_modify: list[str]
    files_to_add: list[str] = []
    implementation_steps: list[str]
    test_strategy: list[str]
    risk_level: str = "low"
    complexity: str = "simple"

    @field_validator("risk_level")
    @classmethod
    def validate_risk(cls, v: str) -> str:
        if v not in ("low", "medium", "high"):
            return "medium"
        return v

    @field_validator("complexity")
    @classmethod
    def validate_complexity(cls, v: str) -> str:
        if v not in ("simple", "complex"):
            return "simple"
        return v


PLANNER_SYSTEM = """You are a software planning agent. Analyze the issue and code context,
then produce a JSON plan with these exact fields:
- summary: concise description of what needs to change
- root_cause: why the issue exists
- files_to_modify: list of file paths to change
- files_to_add: list of new file paths (if any)
- implementation_steps: ordered list of changes
- test_strategy: list of test cases needed
- risk_level: low | medium | high
- complexity: simple | complex (use complex for multi-file refactors or architectural changes)

Return ONLY valid JSON."""


def planner(state: AgentState, *, llm, **kwargs) -> dict:
    """Generate a structured plan from issue + code context."""
    log = state.get("execution_log", [])
    log.append("planner: starting")

    issue = state.get("issue", {})
    code_ctx = state.get("code_context", "")

    prompt = (
        f"Issue: {sanitize_for_prompt(issue.get('title', ''))}\n"
        f"Description: {sanitize_for_prompt(issue.get('body', ''))}\n\n"
        f"Code context:\n{sanitize_for_prompt(code_ctx, max_length=8000)}\n\n"
        f"File tree:\n{state.get('file_tree', '')}\n\n"
        "Generate the implementation plan as JSON."
    )

    try:
        response = llm.generate(prompt, system=PLANNER_SYSTEM)
        plan_data = _parse_plan(response.content)
        plan = PlanModel(**plan_data)

        log.append(f"planner: created plan - complexity={plan.complexity}, risk={plan.risk_level}")
        log.append(f"planner: {len(plan.implementation_steps)} steps, {len(plan.files_to_modify)} files")

        return {
            "plan": plan.model_dump(),
            "complexity": plan.complexity,
            "execution_log": log,
        }
    except Exception as e:
        message = describe_error(e, "OpenAI")
        logger.error("Planner failed: %s", message)
        log.append(f"planner: failed - {message}")
        return {
            "status": "failed",
            "errors": state.get("errors", []) + [message],
            "execution_log": log,
        }


def _parse_plan(content: str) -> dict:
    """Extract JSON from LLM response, handling markdown code fences."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        content = "\n".join(lines)
    return json.loads(content)
