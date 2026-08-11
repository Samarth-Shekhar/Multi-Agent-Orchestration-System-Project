"""Planner Agent — creates structured implementation plan from issue + code context."""

from __future__ import annotations

import logging

from pydantic import BaseModel, field_validator

from gitpilot.errors import describe_error
from gitpilot.llm.json_response import parse_json_response
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

    @field_validator(
        "files_to_modify",
        "files_to_add",
        "implementation_steps",
        "test_strategy",
        mode="before",
    )
    @classmethod
    def normalize_string_lists(cls, value):
        """Accept the small object wrappers commonly emitted by local models."""
        if not isinstance(value, list):
            return value

        preferred_keys = ("path", "file", "step", "test_case", "description", "name")
        normalized = []
        for item in value:
            if isinstance(item, str):
                normalized.append(item)
                continue
            if isinstance(item, dict):
                text = next(
                    (
                        item[key]
                        for key in preferred_keys
                        if isinstance(item.get(key), str) and item[key].strip()
                    ),
                    None,
                )
                normalized.append(text if text is not None else str(item))
                continue
            normalized.append(str(item))
        return normalized

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
- implementation_steps: ordered list of change strings (strings only, not objects)
- test_strategy: list of test-case strings (strings only, not objects)
- risk_level: low | medium | high
- complexity: simple | complex (use complex for multi-file refactors or architectural changes)

Keep the plan compact: at most 5 implementation steps and 4 test cases, with each
string limited to one concise sentence.
JSON-escape every backslash inside string values (for example, write \\ as \\\\).
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
        message = describe_error(e, llm.name())
        logger.error("Planner failed: %s", message)
        log.append(f"planner: failed - {message}")
        return {
            "status": "failed",
            "errors": state.get("errors", []) + [message],
            "execution_log": log,
        }


def _parse_plan(content: str) -> dict:
    """Extract JSON from LLM response, handling markdown code fences."""
    return parse_json_response(content)
