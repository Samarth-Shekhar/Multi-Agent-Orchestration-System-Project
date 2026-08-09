"""Integration test for full demo workflow."""

from gitpilot.demo import run_demo


def test_demo_integration():
    """Ensure the zero-cost demo runner executes without errors."""
    exit_code = run_demo()
    assert exit_code == 0
