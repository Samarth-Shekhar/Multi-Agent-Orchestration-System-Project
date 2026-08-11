"""GitHub REST API client."""

from __future__ import annotations

import base64
import logging
import stat
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GitHubIssue:
    number: int
    title: str
    body: str
    labels: list[str]
    url: str


@dataclass
class GitHubRepo:
    full_name: str
    default_branch: str
    clone_url: str
    language: str | None


class GitHubClient:
    """Thin wrapper around GitHub REST API v3."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str = ""):
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers=headers,
            follow_redirects=True,
            timeout=30.0,
        )
        self._has_token = bool(token)

    def get_issue(self, owner: str, repo: str, number: int) -> GitHubIssue:
        resp = self._client.get(f"/repos/{owner}/{repo}/issues/{number}")
        resp.raise_for_status()
        data = resp.json()
        return GitHubIssue(
            number=data["number"],
            title=data["title"],
            body=data.get("body", "") or "",
            labels=[label["name"] for label in data.get("labels", [])],
            url=data["html_url"],
        )

    def get_repo(self, owner: str, repo: str) -> GitHubRepo:
        resp = self._client.get(f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        data = resp.json()
        return GitHubRepo(
            full_name=data["full_name"],
            default_branch=data["default_branch"],
            clone_url=data["clone_url"],
            language=data.get("language"),
        )

    def download_repository(
        self, owner: str, repo: str, branch: str, destination: Path
    ) -> None:
        """Download and safely extract one GitHub branch into destination."""
        resp = self._client.get(f"/repos/{owner}/{repo}/zipball/{branch}")
        resp.raise_for_status()
        if len(resp.content) > 100 * 1024 * 1024:
            raise ValueError("Repository archive exceeds the 100 MB safety limit")

        destination.mkdir(parents=True, exist_ok=False)
        destination_root = destination.resolve()
        with zipfile.ZipFile(BytesIO(resp.content)) as archive:
            for member in archive.infolist():
                # GitHub wraps archives in owner-repo-sha/. Strip that folder.
                parts = Path(member.filename).parts
                if len(parts) < 2:
                    continue
                relative = Path(*parts[1:])
                target = (destination_root / relative).resolve()
                if destination_root not in target.parents and target != destination_root:
                    raise ValueError(f"Unsafe path in repository archive: {member.filename}")
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    continue
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)

    def create_branch(self, owner: str, repo: str, branch: str, from_sha: str) -> None:
        resp = self._client.post(
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": from_sha},
        )
        resp.raise_for_status()

    def get_default_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        resp = self._client.get(f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
        resp.raise_for_status()
        return resp.json()["object"]["sha"]

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> str:
        resp = self._client.post(
            f"/repos/{owner}/{repo}/pulls",
            json={"title": title, "body": body, "head": head, "base": base},
        )
        resp.raise_for_status()
        return resp.json()["html_url"]

    def upsert_file(
        self, owner: str, repo: str, path: str, content: bytes, branch: str, message: str
    ) -> None:
        """Create or update one repository file on a branch through GitHub Contents API."""
        existing = self._client.get(
            f"/repos/{owner}/{repo}/contents/{path}", params={"ref": branch}
        )
        payload = {
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
            "branch": branch,
        }
        if existing.status_code == 200:
            payload["sha"] = existing.json()["sha"]
        elif existing.status_code != 404:
            existing.raise_for_status()
        resp = self._client.put(f"/repos/{owner}/{repo}/contents/{path}", json=payload)
        resp.raise_for_status()

    @staticmethod
    def parse_repo_url(url: str) -> tuple[str, str]:
        """Extract owner and repo name from a GitHub URL."""
        parsed = urlparse(url.strip())
        if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise ValueError(f"Cannot parse GitHub repo URL: {url}")
        parts = [part for part in parsed.path.rstrip("/").split("/") if part]
        if len(parts) != 2:
            raise ValueError(f"Expected https://github.com/owner/repository, got: {url}")
        return parts[0], parts[1].removesuffix(".git")

    def close(self) -> None:
        self._client.close()


class MockGitHubClient:
    """Mock GitHub client for demo/test mode."""

    def __init__(self):
        self._has_token = False

    def get_issue(self, owner: str, repo: str, number: int) -> GitHubIssue:
        return GitHubIssue(
            number=number,
            title="Calculator divide() crashes when denominator is zero",
            body=(
                "When calling `calculator.divide(10, 0)`, the application crashes with "
                "an unhandled ZeroDivisionError.\n\n"
                "Expected: Return a clear ValueError with a descriptive message.\n\n"
                "Also add regression tests to prevent this from recurring."
            ),
            labels=["bug", "good-first-issue"],
            url=f"https://github.com/{owner}/{repo}/issues/{number}",
        )

    def get_repo(self, owner: str, repo: str) -> GitHubRepo:
        return GitHubRepo(
            full_name=f"{owner}/{repo}",
            default_branch="main",
            clone_url=f"https://github.com/{owner}/{repo}.git",
            language="Python",
        )

    def create_branch(self, owner: str, repo: str, branch: str, from_sha: str) -> None:
        logger.info("[DRY RUN] Would create branch: %s", branch)

    def get_default_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        return "abc123def456"

    def create_pull_request(self, owner: str, repo: str, title: str, body: str, head: str, base: str) -> str:
        pr_url = f"https://github.com/{owner}/{repo}/pull/42"
        logger.info("[DRY RUN] Would create PR: %s", pr_url)
        return pr_url

    @staticmethod
    def parse_repo_url(url: str) -> tuple[str, str]:
        return GitHubClient.parse_repo_url(url)

    def close(self) -> None:
        pass
