"""Code Reader Agent — analyzes repository structure and retrieves relevant context."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from gitpilot.security import is_path_safe
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)

# Directories/files to skip during analysis
IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "dist", "build",
    "coverage", "__pycache__", ".pytest_cache", ".tox", ".eggs",
    ".mypy_cache", ".ruff_cache", "htmlcov", ".next", "target",
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".o",
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".bz2",
    ".pdf", ".doc", ".docx",
    ".lock",
}

MAX_FILE_SIZE = 50_000  # chars
MAX_CONTEXT_FILES = 15


def code_reader(state: AgentState, *, llm=None, **kwargs) -> dict:
    """Analyze repo structure and retrieve relevant files for the issue."""
    log = state.get("execution_log", [])
    log.append("code_reader: starting")

    repo_path = state.get("repo_path", "")
    issue = state.get("issue", {})
    issue_text = f"{issue.get('title', '')} {issue.get('body', '')}"

    if not repo_path or not Path(repo_path).exists():
        log.append("code_reader: repo_path not found, using demo mode")
        return _demo_code_read(state, log)

    try:
        tree = _build_file_tree(repo_path)
        relevant = _find_relevant_files(repo_path, issue_text, tree)
        context = _read_file_contents(repo_path, relevant)

        log.append(f"code_reader: scanned {len(tree)} files, retrieved {len(relevant)} relevant")
        return {
            "file_tree": "\n".join(tree),
            "retrieved_files": relevant,
            "code_context": context,
            "execution_log": log,
        }
    except Exception as e:
        log.append(f"code_reader: error - {e}")
        return {
            "status": "failed",
            "errors": state.get("errors", []) + [f"Code read failed: {e}"],
            "execution_log": log,
        }


def _demo_code_read(state: AgentState, log: list) -> dict:
    """Provide demo context when no real repo is available."""
    tree = "calculator.py\ntest_calculator.py\nREADME.md\nsetup.py"
    context = '''# calculator.py
class Calculator:
    def add(self, a: float, b: float) -> float:
        return a + b

    def subtract(self, a: float, b: float) -> float:
        return a - b

    def multiply(self, a: float, b: float) -> float:
        return a * b

    def divide(self, a: float, b: float) -> float:
        return a / b
'''
    files = ["calculator.py"]
    log.append("code_reader: demo mode - loaded fixture context")
    return {
        "file_tree": tree,
        "retrieved_files": files,
        "code_context": context,
        "execution_log": log,
    }


def _build_file_tree(repo_path: str) -> list[str]:
    """Build a filtered file tree of the repository."""
    tree = []
    root = Path(repo_path)
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        rel_dir = Path(dirpath).relative_to(root)
        for f in filenames:
            ext = Path(f).suffix.lower()
            if ext in IGNORE_EXTENSIONS:
                continue
            rel_path = str(rel_dir / f) if str(rel_dir) != "." else f
            tree.append(rel_path)
    return tree


def _find_relevant_files(repo_path: str, issue_text: str, tree: list[str]) -> list[str]:
    """Find files relevant to the issue using heuristic matching."""
    issue_lower = issue_text.lower()
    scored: list[tuple[float, str]] = []

    # Extract keywords from issue
    keywords = set()
    for word in issue_lower.split():
        word = word.strip("()[]{}.,;:\"'`#")
        if len(word) > 2:
            keywords.add(word)

    for filepath in tree:
        score = 0.0
        name = Path(filepath).stem.lower()
        ext = Path(filepath).suffix.lower()

        # Filename matches issue keywords
        for kw in keywords:
            if kw in name:
                score += 10.0
            if kw in filepath.lower():
                score += 3.0

        # Source code files get higher weight
        if ext in {".py", ".js", ".ts", ".go", ".rs", ".java", ".rb"}:
            score += 1.0

        # Test files are relevant
        if "test" in name or "spec" in name:
            score += 2.0

        # Config files
        if name in {"setup", "pyproject", "package", "makefile", "cargo", "go"}:
            score += 1.5

        if score > 0:
            scored.append((score, filepath))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in scored[:MAX_CONTEXT_FILES]]


def _read_file_contents(repo_path: str, files: list[str]) -> str:
    """Read and concatenate file contents with headers."""
    parts = []
    root = Path(repo_path)
    for rel in files:
        full = root / rel
        if not is_path_safe(str(full), repo_path):
            continue
        try:
            content = full.read_text(encoding="utf-8", errors="replace")
            if len(content) > MAX_FILE_SIZE:
                content = content[:MAX_FILE_SIZE] + "\n... [truncated]"
            parts.append(f"# {rel}\n{content}")
        except (OSError, UnicodeDecodeError):
            continue
    return "\n\n".join(parts)
