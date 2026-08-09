"""User-facing error normalization for external services and local tools."""

from __future__ import annotations

import httpx


def describe_error(error: Exception, service: str) -> str:
    """Return a concise actionable message without leaking response details."""
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if service == "GitHub" and status == 404:
            return (
                "GitHub repository or issue not found. Confirm the repository URL, use an "
                "existing issue number, and add GITHUB_TOKEN for private repositories."
            )
        if service == "GitHub" and status == 410:
            return (
                "GitHub issue is gone or was deleted. Choose an existing issue from the "
                "repository's Issues page; deleted issue numbers cannot be processed."
            )
        if service == "OpenAI" and status == 429:
            return (
                "OpenAI quota or rate limit reached. Check API billing and usage limits, "
                "then retry after the limit resets."
            )
        if service == "OpenAI" and status == 401:
            return "OpenAI rejected the API key. Replace OPENAI_API_KEY in .env and restart."
        return f"{service} request failed with HTTP {status}."
    if isinstance(error, FileNotFoundError):
        return f"Required local command was not found: {error.filename or 'unknown command'}."
    return f"{service} failed: {error}"
