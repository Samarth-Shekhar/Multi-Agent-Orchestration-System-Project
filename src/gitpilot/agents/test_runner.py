"""Test Runner Agent — executes tests in a controlled environment."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from gitpilot.errors import describe_error
from gitpilot.state import AgentState

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120  # seconds


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
        result = subprocess.run(
            test_cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT,
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
        return ["npm", "test"]
    if (root / "Makefile").exists():
        return ["make", "test"]
    if (root / "go.mod").exists():
        return ["go", "test", "./..."]
    if (root / "Cargo.toml").exists():
        return ["cargo", "test"]

    return ["python", "-m", "pytest", "-v"]
