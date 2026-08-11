"""Code Writer Agent — generates targeted code changes based on the plan."""

from __future__ import annotations

import logging
from pathlib import Path

from gitpilot.errors import describe_error
from gitpilot.llm.json_response import parse_json_response
from gitpilot.security import sanitize_for_prompt, validate_file_operation
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)

CODE_WRITER_SYSTEM = """You are a code implementation agent. Based on the plan and context,
generate the exact complete content for every modified or new file. Return ONLY valid JSON:
{"files": [{"path": "relative/path.ext", "content": "complete file content"}]}
JSON-escape every backslash inside file content (for example, write \\ as \\\\).
Do not modify unrelated files and never use absolute paths or paths containing '..'."""


def code_writer(state: AgentState, *, llm, **kwargs) -> dict:
    """Generate code modifications based on the plan."""
    log = state.get("execution_log", [])
    log.append("code_writer: starting")

    plan = state.get("plan", {})
    code_ctx = state.get("code_context", "")
    research = state.get("research_notes", "")
    repo_path = state.get("repo_path", "")
    repair_history = state.get("repair_history", [])

    repair_ctx = ""
    if repair_history:
        repair_ctx = f"\n\nPrevious attempt feedback:\n{repair_history[-1]}"

    prompt = (
        f"Plan:\n{sanitize_for_prompt(str(plan), max_length=3000)}\n\n"
        f"Code context:\n{sanitize_for_prompt(code_ctx, max_length=5000)}\n\n"
    )
    if research:
        prompt += f"Research notes:\n{sanitize_for_prompt(research, max_length=2000)}\n\n"
    if repair_ctx:
        prompt += f"Repair context: {repair_ctx}\n\n"

    prompt += "Generate code changes. Write the complete modified code for each file."

    try:
        response = llm.generate(prompt, system=CODE_WRITER_SYSTEM)
        generated_files = _parse_generated_files(response.content)
        patch_content = _format_patch_preview(generated_files)

        # Apply changes if we have a repo path
        changed_files = []
        if llm.name() == "mock":
            # Preview mode must never overwrite real source files with
            # synthetic output. Use Ollama/OpenAI for actual code edits.
            changed_files = plan.get("files_to_modify", []) + plan.get("files_to_add", [])
        elif repo_path and Path(repo_path).exists():
            changed_files = _apply_changes(repo_path, plan, generated_files)
        else:
            changed_files = plan.get("files_to_modify", []) + plan.get("files_to_add", [])

        log.append(f"code_writer: generated patch for {len(changed_files)} files")

        return {
            "patch": patch_content,
            "changed_files": changed_files,
            "diff_summary": f"Modified {len(changed_files)} files based on plan",
            "execution_log": log,
        }
    except Exception as e:
        message = describe_error(e, llm.name())
        logger.error("Code writer failed: %s", message)
        log.append(f"code_writer: failed - {message}")
        return {
            "status": "failed",
            "patch": "",
            "changed_files": [],
            "errors": state.get("errors", []) + [message],
            "execution_log": log,
        }


def _parse_generated_files(content: str) -> list[dict[str, str]]:
    """Parse the LLM's path-to-content response."""
    payload = parse_json_response(content)
    files = payload.get("files", [])
    if not isinstance(files, list) or not files:
        raise ValueError("Code model returned no files")
    parsed = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("Code model returned an invalid file entry")
        if not isinstance(item.get("content"), str):
            raise ValueError(f"Missing content for {item.get('path', 'unknown file')}")
        parsed.append({"path": item["path"], "content": item["content"]})
    return parsed
def _format_patch_preview(files: list[dict[str, str]]) -> str:
    return "\n\n".join(f"# FILE: {item['path']}\n{item['content']}" for item in files)


def _apply_changes(repo_path: str, plan: dict, files: list[dict[str, str]]) -> list[str]:
    """Apply path-scoped generated files inside the isolated workspace."""
    changed = []
    allowed = set(plan.get("files_to_modify", []) + plan.get("files_to_add", []))

    for item in files:
        filepath = item["path"]
        if filepath not in allowed:
            logger.warning("Skipping unplanned generated file: %s", filepath)
            continue
        full_path = Path(repo_path) / filepath
        safe, reason = validate_file_operation(str(full_path), repo_path)
        if not safe:
            logger.warning("Skipping unsafe file: %s (%s)", filepath, reason)
            continue
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(item["content"], encoding="utf-8")
            changed.append(filepath)
        except OSError as e:
            logger.warning("Could not write %s: %s", filepath, e)

    return changed
