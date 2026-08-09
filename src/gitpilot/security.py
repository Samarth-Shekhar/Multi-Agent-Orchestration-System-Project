"""Security utilities for path validation and prompt sanitization."""

from __future__ import annotations

import re
from pathlib import Path

# Paths that should never be modified by agents
FORBIDDEN_PATHS = {
    ".git",
    ".ssh",
    ".gnupg",
    ".bashrc",
    ".bash_profile",
    ".zshrc",
    ".profile",
    ".gitconfig",
}

FORBIDDEN_PATTERNS = [
    r"\.git/",
    r"\.ssh/",
    r"\.gnupg/",
    r"/etc/",
    r"~\/",
    r"\.\./",  # path traversal
]

# Prompt injection patterns
INJECTION_PATTERNS = [
    r"ignore\s+(your\s+)?(previous|prior|all)\s+(instructions|rules|prompts)",
    r"disregard\s+(your\s+)?(previous|prior|all)\s+(instructions|rules|prompts)",
    r"forget\s+(your\s+)?(previous|prior|all)\s+(instructions|rules|prompts)",
    r"you\s+are\s+now\s+",
    r"new\s+instructions?\s*:",
    r"system\s*prompt\s*:",
    r"read\s+~/\.ssh",
    r"cat\s+/etc/(passwd|shadow)",
    r"send\s+(environment|env)\s+variables",
    r"curl\s+.*\|\s*(sh|bash)",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__",
    r"subprocess\.(call|run|Popen)",
]

_compiled_injection = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def is_path_safe(path: str | Path, workspace_root: str | Path) -> bool:
    """Validate path is within workspace and not forbidden."""
    try:
        resolved = Path(path).resolve()
        workspace = Path(workspace_root).resolve()

        # Must be inside workspace
        if not str(resolved).startswith(str(workspace)):
            return False

        # Check forbidden paths
        rel = resolved.relative_to(workspace)
        parts = rel.parts
        for part in parts:
            if part in FORBIDDEN_PATHS:
                return False
            for pattern in FORBIDDEN_PATTERNS:
                if re.search(pattern, str(rel)):
                    return False

        return True
    except (ValueError, OSError):
        return False


def detect_prompt_injection(text: str) -> list[str]:
    """Scan text for prompt injection attempts. Returns list of matched patterns."""
    findings = []
    for pattern in _compiled_injection:
        if pattern.search(text):
            findings.append(pattern.pattern)
    return findings


def sanitize_for_prompt(text: str, max_length: int = 10000) -> str:
    """Sanitize untrusted text before including in LLM prompts."""
    # Truncate
    if len(text) > max_length:
        text = text[:max_length] + "\n... [truncated]"

    # Wrap in clear data boundary markers
    return f"<user_data>\n{text}\n</user_data>"


def validate_file_operation(filepath: str, workspace_root: str) -> tuple[bool, str]:
    """Validate a file operation is safe to perform."""
    if not is_path_safe(filepath, workspace_root):
        return False, f"Path outside workspace or forbidden: {filepath}"

    # Check for suspicious extensions
    suspicious = {".sh", ".bash", ".bat", ".cmd", ".ps1", ".exe", ".dll", ".so"}
    suffix = Path(filepath).suffix.lower()
    if suffix in suspicious:
        return False, f"Suspicious file extension: {suffix}"

    return True, "ok"
