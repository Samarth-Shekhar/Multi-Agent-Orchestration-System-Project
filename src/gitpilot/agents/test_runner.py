"""Test Runner Agent — executes tests in a controlled environment."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from gitpilot.errors import describe_error
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120  # seconds
DEPENDENCY_TIMEOUT = 300  # seconds
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_runner(state: AgentState, **kwargs) -> dict:
    """Run tests and capture results."""
    log = state.get("execution_log", [])
    attempt = state.get("attempt_count", 0) + 1
    log.append(f"test_runner: starting (attempt {attempt})")

    repo_path = state.get("repo_path", "")

    if not repo_path or not Path(repo_path).exists():
        return _simulate_test_run(state, log, attempt)

    test_cmd = _detect_test_command(repo_path)
    log.append(f"test_runner: using command '{' '.join(test_cmd)}'")

    start = time.time()
    try:
        dependency_error = _prepare_javascript_dependencies(repo_path, test_cmd, log)
        if dependency_error:
            raise RuntimeError(dependency_error)
        result = subprocess.run(
            test_cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT,
            env=_command_environment(test_cmd),
        )
        duration = time.time() - start
        passed = result.returncode == 0

        log.append(f"test_runner: {'PASSED' if passed else 'FAILED'} in {duration:.1f}s")

        return {
            "test_results": {
                "passed": passed,
                "stdout": result.stdout[-3000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
                "exit_code": result.returncode,
                "duration_seconds": round(duration, 2),
                "framework": "pytest",
                "command": " ".join(test_cmd),
            },
            "attempt_count": attempt,
            "execution_log": log,
        }
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        log.append(f"test_runner: TIMEOUT after {duration:.1f}s")
        return {
            "test_results": {
                "passed": False,
                "stdout": "",
                "stderr": "Test execution timed out",
                "exit_code": -1,
                "duration_seconds": round(duration, 2),
                "framework": "pytest",
                "command": " ".join(test_cmd),
            },
            "attempt_count": attempt,
            "execution_log": log,
        }
    except Exception as e:
        message = describe_error(e, "Test runner")
        log.append(f"test_runner: failed - {message}")
        return {
            "status": "failed",
            "test_results": {
                "passed": False,
                "stdout": "",
                "stderr": message,
                "exit_code": -1,
                "duration_seconds": 0,
                "framework": "unknown",
                "command": " ".join(test_cmd),
            },
            "attempt_count": attempt,
            "errors": state.get("errors", []) + [message],
            "execution_log": log,
        }


def _simulate_test_run(state: AgentState, log: list, attempt: int) -> dict:
    """Simulate test execution for demo mode."""
    log.append("test_runner: demo mode - simulating test execution")

    # In demo mode, tests pass on first attempt
    return {
        "test_results": {
            "passed": True,
            "stdout": (
                "============================= test session starts ==============================\n"
                "collected 4 items\n\n"
                "test_calculator.py::TestDivide::test_divide_normal PASSED\n"
                "test_calculator.py::TestDivide::test_divide_negative PASSED\n"
                "test_calculator.py::TestDivide::test_divide_by_zero_raises PASSED\n"
                "test_calculator.py::TestDivide::test_divide_zero_numerator PASSED\n\n"
                "============================== 4 passed in 0.12s ==============================\n"
            ),
            "stderr": "",
            "exit_code": 0,
            "duration_seconds": 0.12,
            "framework": "pytest",
            "command": "pytest test_calculator.py -v",
        },
        "attempt_count": attempt,
        "execution_log": log,
    }


def _detect_test_command(repo_path: str) -> list[str]:
    """Detect the test command from project files."""
    root = Path(repo_path)

    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists():
        return ["python", "-m", "pytest", "-v", "--tb=short"]
    if (root / "package.json").exists():
        command = [_find_command("npm", "npm.cmd"), "test"]
        try:
            package = json.loads((root / "package.json").read_text(encoding="utf-8"))
            test_script = package.get("scripts", {}).get("test", "")
            if "jest" in test_script.lower():
                command.extend(["--", "--runInBand"])
        except (OSError, ValueError, TypeError):
            pass
        return command
    if (root / "Makefile").exists():
        return ["make", "test"]
    if (root / "go.mod").exists():
        return ["go", "test", "./..."]
    if (root / "Cargo.toml").exists():
        return ["cargo", "test"]

    return ["python", "-m", "pytest", "-v"]


def _find_command(command: str, portable_name: str) -> str:
    """Resolve a system command or a project-local portable tool."""
    installed = shutil.which(command)
    if installed:
        return installed

    candidates = sorted((PROJECT_ROOT / ".tools").glob(f"node-*/{portable_name}"))
    if candidates:
        return str(candidates[-1].resolve())
    return command


def _command_environment(command: list[str]) -> dict[str, str]:
    env = os.environ.copy()
    executable = Path(command[0])
    if executable.name.lower() in {"npm.cmd", "npm.exe"} and executable.is_absolute():
        env["PATH"] = f"{executable.parent}{os.pathsep}{env.get('PATH', '')}"
    return env


def _prepare_javascript_dependencies(
    repo_path: str, test_cmd: list[str], log: list[str]
) -> str | None:
    """Install missing npm dependencies without running package lifecycle scripts."""
    root = Path(repo_path)
    if not (root / "package.json").exists():
        return None
    if (root / "node_modules").exists():
        return None

    snapshot = _dependency_snapshot(root)
    if snapshot.exists():
        log.append("test_runner: restoring cached npm dependencies")
        if _create_directory_junction(root / "node_modules", snapshot):
            log.append("test_runner: cached npm dependencies restored")
            return None
        log.append("test_runner: dependency cache unavailable")

    npm = test_cmd[0]
    log.append("test_runner: installing npm dependencies (lifecycle scripts disabled)")
    npm_env = os.environ.copy()
    npm_env.pop("NPM_CONFIG_OFFLINE", None)
    npm_env.pop("npm_config_offline", None)
    shared_cache = PROJECT_ROOT / ".tools" / "npm-cache"
    shared_cache.mkdir(parents=True, exist_ok=True)
    npm_env["NPM_CONFIG_CACHE"] = str(shared_cache.resolve())
    npm_env["NPM_CONFIG_PREFER_ONLINE"] = "true"
    try:
        result = subprocess.run(
            [
                npm,
                "install",
                "--ignore-scripts",
                "--legacy-peer-deps",
                "--no-audit",
                "--no-fund",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=DEPENDENCY_TIMEOUT,
            env=npm_env,
        )
    except subprocess.TimeoutExpired:
        return f"npm dependency installation timed out after {DEPENDENCY_TIMEOUT} seconds"
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "unknown npm error")[-1500:]
        return f"npm dependency installation failed: {details}"
    log.append("test_runner: npm dependencies installed")
    _store_dependency_snapshot(root, snapshot, log)
    return None


def _dependency_snapshot(root: Path) -> Path:
    digest = hashlib.sha256()
    digest.update(os.name.encode())
    manifests = ["package.json"]
    if (root / "yarn.lock").exists():
        manifests.append("yarn.lock")
    elif (root / "npm-shrinkwrap.json").exists():
        manifests.append("npm-shrinkwrap.json")
    elif (root / "package-lock.json").exists():
        manifests.append("package-lock.json")
    for name in manifests:
        manifest = root / name
        if manifest.exists():
            digest.update(name.encode())
            digest.update(manifest.read_bytes())
    return PROJECT_ROOT / ".tools" / "n" / digest.hexdigest()[:16] / "node_modules"


def _store_dependency_snapshot(root: Path, snapshot: Path, log: list[str]) -> None:
    if snapshot.exists():
        return
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    modules = root / "node_modules"
    try:
        modules.rename(snapshot)
        if _create_directory_junction(modules, snapshot):
            log.append("test_runner: npm dependency snapshot cached")
            return
        snapshot.rename(modules)
        log.append("test_runner: could not link dependency snapshot")
    except OSError as error:
        if snapshot.exists() and not modules.exists():
            snapshot.rename(modules)
        log.append(f"test_runner: could not cache dependency snapshot ({error})")


def _create_directory_junction(link: Path, target: Path) -> bool:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0 and link.exists()
