"""Utilities for parsing slightly malformed JSON returned by local LLMs."""

from __future__ import annotations

import json


def parse_json_response(content: str):
    """Parse JSON, removing code fences and repairing invalid code backslashes."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(
            line for line in cleaned.splitlines() if not line.startswith("```")
        )
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Local coding models commonly emit raw regex backslashes and literal
        # newlines/tabs inside JSON string values. Python's non-strict parser
        # accepts the latter after invalid backslashes have been repaired.
        return json.loads(_escape_invalid_backslashes(cleaned), strict=False)


def _escape_invalid_backslashes(content: str) -> str:
    valid_escapes = {'"', "\\", "/", "b", "f", "n", "r", "t", "u"}
    repaired = []
    for index, char in enumerate(content):
        if char == "\\" and (
            index + 1 == len(content) or content[index + 1] not in valid_escapes
        ):
            repaired.append("\\")
        repaired.append(char)
    return "".join(repaired)
