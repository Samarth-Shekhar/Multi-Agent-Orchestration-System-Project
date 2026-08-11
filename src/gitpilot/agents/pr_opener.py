"""PR Opener Agent — creates GitHub pull request from completed workflow."""

from __future__ import annotations

import logging
from pathlib import Path

from gitpilot.security import is_path_safe
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)


def pr_opener(state: AgentState, *, github_client, dry_run: bool = True, **kwargs) -> dict:
    """Create or simulate PR creation."""
    log = state.get("execution_log", [])
    log.append("pr_opener: starting")

    issue = state.get("issue", {})
    plan = state.get("plan", {})
    test_results = state.get("test_results", {})
    review = state.get("review_feedback", {})
    repo_url = state.get("repository_url", "")
    changed_files = state.get("changed_files", [])

    # Build PR content
    issue_num = issue.get("number", 0)
    title = f"fix: {plan.get('summary', issue.get('title', 'Fix issue'))}"
    title = title[:72]  # Keep title concise

    body = _build_pr_body(issue, plan, changed_files, test_results, review, issue_num)
    branch_name = f"gitpilot/fix-{issue_num}"

    if dry_run:
        log.append(f"pr_opener: DRY RUN - would create PR '{title}'")
        log.append(f"pr_opener: branch={branch_name}")

        pr_url = f"[DRY RUN] PR would be created: {title}"
        return {
            "branch_name": branch_name,
            "pr_url": pr_url,
            "pr_body": body,
            "status": "success",
            "execution_log": log,
        }

    # Real PR creation
    try:
        owner, repo = github_client.parse_repo_url(repo_url)
        default_branch = state.get("default_branch", "main")

        sha = github_client.get_default_branch_sha(owner, repo, default_branch)
        github_client.create_branch(owner, repo, branch_name, sha)
        repo_path = state.get("repo_path", "")
        committed_files = []
        for relative_path in changed_files:
            local_file = Path(repo_path) / relative_path
            if not local_file.is_file() or not is_path_safe(str(local_file), repo_path):
                continue
            github_client.upsert_file(
                owner,
                repo,
                relative_path.replace("\\", "/"),
                local_file.read_bytes(),
                branch_name,
                f"fix: update {relative_path}",
            )
            committed_files.append(relative_path)
        if not committed_files:
            raise ValueError("No generated files were available to commit")
        pr_url = github_client.create_pull_request(
            owner=owner,
            repo=repo,
            title=title,
            body=body,
            head=branch_name,
            base=default_branch,
        )

        log.append(f"pr_opener: created PR at {pr_url}")
        return {
            "branch_name": branch_name,
            "pr_url": pr_url,
            "pr_body": body,
            "status": "success",
            "execution_log": log,
        }
    except Exception as e:
        logger.error("PR creation failed: %s", e)
        log.append(f"pr_opener: failed - {e}")
        return {
            "branch_name": branch_name,
            "pr_body": body,
            "status": "failed",
            "errors": state.get("errors", []) + [f"PR creation failed: {e}"],
            "execution_log": log,
        }


def _build_pr_body(
    issue: dict,
    plan: dict,
    changed_files: list[str],
    test_results: dict,
    review: dict,
    issue_num: int,
) -> str:
    """Build a structured PR body."""
    files_list = "\n".join(f"- `{f}`" for f in changed_files) if changed_files else "- No files listed"
    test_status = "[PASSED]" if test_results.get("passed") else "[FAILED]"
    review_status = "[APPROVED]" if review.get("approved") else "[CHANGES REQUESTED]"

    return f"""## Summary

{plan.get('summary', 'Fix applied')}

**Root cause:** {plan.get('root_cause', 'See issue')}

## Changes

{files_list}

### Implementation
{chr(10).join(f'- {s}' for s in plan.get('implementation_steps', []))}

## Tests

{test_status}
{test_results.get('stdout', '')[-500:] if test_results.get('stdout') else ''}

## Review

{review_status}
{review.get('summary', '')}

## Agent Execution

This change was prepared using the **GitPilot** autonomous workflow.
It should receive **human review** before merging.

Closes #{issue_num}
"""
