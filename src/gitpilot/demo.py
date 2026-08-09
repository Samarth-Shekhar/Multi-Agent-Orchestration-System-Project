"""GitPilot free demo runner.

Runs the complete multi-agent workflow on the local fixture repository
without network calls, paid APIs, or GitHub credentials.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from gitpilot.github.client import MockGitHubClient
from gitpilot.llm.mock import MockLLMProvider
from gitpilot.workflow import run_workflow

console = Console()


def run_demo() -> int:
    """Execute the zero-cost demo workflow."""
    console.print(Panel.fit(
        "[bold magenta]GitPilot Multi-Agent Orchestrator[/bold magenta]\n"
        "[dim]Zero-Cost Demo Mode - Local Mock LLM & Fixture Repository[/dim]",
        border_style="magenta",
    ))

    # Path to demo repo fixture
    repo_path = str(Path(__file__).parent.parent.parent / "examples" / "demo_repo")

    llm = MockLLMProvider()
    gh = MockGitHubClient()

    console.print("\n[bold cyan]>> Starting Multi-Agent Workflow...[/bold cyan]\n")

    result = run_workflow(
        repository_url="https://github.com/demo-org/calculator",
        issue_number=1,
        llm=llm,
        github_client=gh,
        dry_run=True,
        max_attempts=3,
        repo_path=repo_path,
    )

    # Display Execution Log
    console.print("\n[bold yellow]State Transitions & Execution Log:[/bold yellow]")
    for log_entry in result.get("execution_log", []):
        console.print(f"  [dim]*[/dim] {log_entry}")

    # Summary Table
    console.print("\n[bold green]Workflow Execution Summary:[/bold green]")
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    plan = result.get("plan", {})
    test_res = result.get("test_results", {})
    review = result.get("review_feedback", {})

    table.add_row("Status", f"[bold green]{result.get('status', 'unknown').upper()}[/bold green]")
    table.add_row("Issue", f"#{result['issue']['number']}: {result['issue']['title']}")
    table.add_row("Plan Summary", plan.get("summary", "N/A"))
    table.add_row("Complexity Route", result.get("complexity", "simple"))
    table.add_row("Files Modified", ", ".join(result.get("changed_files", [])))
    table.add_row("Tests Outcome", "PASSED" if test_res.get("passed") else "FAILED")
    table.add_row("Review Outcome", "APPROVED" if review.get("approved") else "CHANGES REQUESTED")
    table.add_row("Branch Created", result.get("branch_name", "N/A"))
    table.add_row("PR Link", result.get("pr_url", "N/A"))

    console.print(table)

    # Generated PR Body Preview
    if result.get("pr_body"):
        console.print("\n[bold cyan]Generated Pull Request Body:[/bold cyan]")
        console.print(Panel(result["pr_body"], title="PR Description", border_style="cyan"))

    console.print("\n[bold green]Demo completed successfully![/bold green]\n")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(run_demo())
