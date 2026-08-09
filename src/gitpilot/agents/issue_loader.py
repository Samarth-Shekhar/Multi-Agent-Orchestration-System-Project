"""Issue Loader — fetches issue from GitHub and initializes state."""

from __future__ import annotations

import logging

from gitpilot.errors import describe_error
from gitpilot.security import detect_prompt_injection
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)


def issue_loader(state: AgentState, *, github_client, **kwargs) -> dict:
    """Load a GitHub issue and populate initial state."""
    log = state.get("execution_log", [])
    log.append("issue_loader: starting")

    repo_url = state["repository_url"]
    owner, repo = github_client.parse_repo_url(repo_url)

    issue_num = state["issue"]["number"]
    logger.info("Loading issue #%d from %s/%s", issue_num, owner, repo)

    try:
        gh_issue = github_client.get_issue(owner, repo, issue_num)
        gh_repo = github_client.get_repo(owner, repo)
    except Exception as e:
        message = describe_error(e, "GitHub")
        log.append(f"issue_loader: failed - {message}")
        return {
            "status": "failed",
            "errors": state.get("errors", []) + [message],
            "execution_log": log,
        }

    # Check issue text for injection attempts
    injections = detect_prompt_injection(gh_issue.body)
    if injections:
        logger.warning("Prompt injection detected in issue body: %s", injections)
        log.append(f"issue_loader: prompt injection detected ({len(injections)} patterns)")

    log.append(f"issue_loader: loaded issue #{gh_issue.number} - {gh_issue.title}")

    return {
        "issue": {
            "number": gh_issue.number,
            "title": gh_issue.title,
            "body": gh_issue.body,
            "labels": gh_issue.labels,
            "url": gh_issue.url,
        },
        "repository_url": repo_url,
        "default_branch": gh_repo.default_branch,
        "status": "running",
        "execution_log": log,
    }
