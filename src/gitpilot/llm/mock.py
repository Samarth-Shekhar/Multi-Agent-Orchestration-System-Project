"""Deterministic mock LLM for testing and demo mode."""

from __future__ import annotations

import json
import re

from gitpilot.llm.base import BaseLLMProvider, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """Returns deterministic responses based on prompt content & system roles.

    Used for automated tests and zero-cost demo mode.
    """

    def name(self) -> str:
        return "mock"

    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        system_lower = system.lower()
        prompt_lower = prompt.lower()

        # System-role based routing (100% precise)
        if "planning" in system_lower:
            return self._plan_response(prompt_lower)
        if "research" in system_lower:
            return self._research_response(prompt)
        if "implementation" in system_lower or "code writer" in system_lower:
            return self._code_response(prompt_lower)
        if "test writing" in system_lower:
            return self._test_response(prompt_lower)
        if "review" in system_lower:
            return self._review_response(prompt)
        if "repair" in system_lower:
            return self._code_response(prompt_lower)

        # Fallback keyword matching for raw prompts
        if "review" in prompt_lower:
            return self._review_response(prompt)
        if "plan" in prompt_lower:
            return self._plan_response(prompt_lower)
        if "write code" in prompt_lower or "patch" in prompt_lower:
            return self._code_response(prompt_lower)
        if "test" in prompt_lower:
            return self._test_response(prompt_lower)

        return LLMResponse(content="Mock response for unmatched prompt.", model="mock")

    def _plan_response(self, prompt: str) -> LLMResponse:
        complexity = "complex" if any(w in prompt for w in ["refactor", "redesign", "architecture"]) else "simple"
        issue = self._field(prompt, "issue") or "the reported issue"
        files = self._candidate_files(prompt)
        target = files[0] if files else "source file identified during implementation"

        plan = {
            "summary": f"Address: {issue}",
            "root_cause": f"The behavior reported in '{issue}' requires validation against the repository code.",
            "files_to_modify": [target] if files else [],
            "files_to_add": [],
            "implementation_steps": [
                f"Inspect the relevant behavior in {target}",
                f"Implement the smallest change that addresses: {issue}",
                "Preserve existing public behavior and error handling",
            ],
            "test_strategy": [
                f"Add a regression test for: {issue}",
                "Verify the existing happy path still works",
                "Verify invalid and boundary inputs are handled",
            ],
            "risk_level": "low",
            "complexity": complexity,
        }
        return LLMResponse(content=json.dumps(plan), model="mock")

    def _research_response(self, prompt: str) -> LLMResponse:
        subject = self._field(prompt, "plan") or "the submitted issue"
        notes = (
            f"Repository-specific research preview for {subject[:160]}:\n"
            "- Review the retrieved source files and their direct callers\n"
            "- Preserve the repository's existing framework and conventions\n"
            "- Confirm the proposed behavior with a focused regression test"
        )
        return LLMResponse(content=notes, model="mock")

    def _code_response(self, prompt: str) -> LLMResponse:
        summary = self._field(prompt, "plan") or "Apply the submitted issue fix"
        files = self._candidate_files(prompt)
        target = files[0] if files else "<relevant-source-file>"
        code = (
            "# MOCK PREVIEW — no repository files were modified\n"
            f"# Target: {target}\n"
            f"# Requested change: {summary[:300]}\n\n"
            "# Configure LLM_PROVIDER=ollama or LLM_PROVIDER=openai to generate\n"
            "# an exact, repository-aware implementation for this issue."
        )
        return LLMResponse(
            content=json.dumps({"files": [{"path": target, "content": code}]}), model="mock"
        )

    def _test_response(self, prompt: str) -> LLMResponse:
        subject = self._field(prompt, "plan") or "submitted issue"
        tests = (
            "# MOCK TEST PREVIEW — not written to the repository\n"
            f"# Regression target: {subject[:300]}\n"
            "# 1. Reproduce the reported failure\n"
            "# 2. Assert the corrected behavior\n"
            "# 3. Confirm existing behavior remains unchanged"
        )
        return LLMResponse(content=tests, model="mock")

    def _review_response(self, prompt: str) -> LLMResponse:
        issue = self._field(prompt, "issue") or "the submitted issue"
        review = {
            "approved": True,
            "issues": [],
            "summary": f"Mock preview reviewed for alignment with: {issue}. Use a configured LLM for a substantive code review.",
        }
        return LLMResponse(content=json.dumps(review), model="mock")

    @staticmethod
    def _field(prompt: str, name: str) -> str:
        match = re.search(rf"^{re.escape(name)}:\s*(.*)$", prompt, re.IGNORECASE | re.MULTILINE)
        if not match:
            return ""
        value = match.group(1).strip()
        if value == "<user_data>":
            remainder = prompt[match.end() :]
            end = remainder.find("</user_data>")
            return remainder[:end].strip() if end >= 0 else ""
        return value

    @staticmethod
    def _candidate_files(prompt: str) -> list[str]:
        matches = re.findall(
            r"(?<![\w/.-])([\w./-]+\.(?:py|js|jsx|ts|tsx|go|rs|java|rb|php|vue|svelte))",
            prompt,
            re.IGNORECASE,
        )
        ignored = {"package.json", "pyproject.toml"}
        return list(dict.fromkeys(path for path in matches if path not in ignored))[:3]
