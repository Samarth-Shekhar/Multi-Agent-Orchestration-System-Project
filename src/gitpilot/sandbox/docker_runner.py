"""Docker sandbox runner for executing tests on external repositories."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float


class DockerSandboxRunner:
    """Execute commands inside a restricted Docker container."""

    DEFAULT_IMAGE = "python:3.12-slim"
    CPU_LIMIT = "1.0"
    MEMORY_LIMIT = "512m"
    TIMEOUT = 120

    def __init__(self, image: str = DEFAULT_IMAGE):
        self.image = image

    def is_available(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def run(
        self,
        command: list[str],
        workspace: str | Path,
        timeout: int | None = None,
        network: bool = False,
    ) -> SandboxResult:
        """Run a command inside a Docker container with restrictions."""
        import time

        workspace = Path(workspace).resolve()
        timeout = timeout or self.TIMEOUT

        docker_cmd = [
            "docker", "run",
            "--rm",
            "--cpus", self.CPU_LIMIT,
            "--memory", self.MEMORY_LIMIT,
            "--pids-limit", "100",
            "--read-only",
            "--tmpfs", "/tmp:size=100m",
            "-v", f"{workspace}:/workspace:ro",
            "-w", "/workspace",
        ]

        if not network:
            docker_cmd.append("--network=none")

        # Security: no privileged, no docker socket, no host mounts
        docker_cmd.extend([
            "--security-opt", "no-new-privileges",
            self.image,
        ])
        docker_cmd.extend(command)

        logger.info("Sandbox executing: %s", " ".join(command))

        start = time.time()
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = time.time() - start
            return SandboxResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration_seconds=round(duration, 2),
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - start
            return SandboxResult(
                stdout="",
                stderr="Sandbox execution timed out",
                exit_code=-1,
                duration_seconds=round(duration, 2),
            )

    @staticmethod
    def build_test_command(workspace: str | Path) -> list[str]:
        """Detect and return appropriate test command for the workspace."""
        root = Path(workspace)
        if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists():
            return ["python", "-m", "pytest", "-v", "--tb=short"]
        if (root / "package.json").exists():
            return ["npm", "test"]
        if (root / "go.mod").exists():
            return ["go", "test", "./..."]
        return ["python", "-m", "pytest", "-v"]
