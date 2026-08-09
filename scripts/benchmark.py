"""Benchmark script to measure real local demo performance metrics."""

import time
import json
from pathlib import Path

from gitpilot.llm.mock import MockLLMProvider
from gitpilot.github.client import MockGitHubClient
from gitpilot.workflow import run_workflow


def run_benchmark():
    repo_path = str(Path(__file__).parent.parent / "examples" / "demo_repo")
    llm = MockLLMProvider()
    gh = MockGitHubClient()

    start_time = time.time()
    result = run_workflow(
        repository_url="https://github.com/demo-org/calculator",
        issue_number=1,
        llm=llm,
        github_client=gh,
        dry_run=True,
        max_attempts=3,
        repo_path=repo_path,
    )
    elapsed = time.time() - start_time

    logs = result.get("execution_log", [])
    transitions = len([l for l in logs if "starting" in l or "loaded" in l])
    retrieved = len(result.get("retrieved_files", []))
    files_mod = len(result.get("changed_files", []))
    repair_attempts = result.get("attempt_count", 0)

    print("=" * 50)
    print("LOCAL DEMO BENCHMARK RESULTS")
    print("=" * 50)
    print(f"Workflow Duration:      {elapsed * 1000:.2f} ms")
    print(f"State Transitions:      {transitions}")
    print(f"Retrieved Files:        {retrieved}")
    print(f"Files Modified:         {files_mod}")
    print(f"Repair Attempts:        {repair_attempts}")
    print(f"Status:                 {result.get('status')}")
    print("=" * 50)

    metrics = {
        "duration_ms": round(elapsed * 1000, 2),
        "state_transitions": transitions,
        "retrieved_files": retrieved,
        "files_modified": files_mod,
        "repair_attempts": repair_attempts,
        "status": result.get("status"),
    }

    out_file = Path(__file__).parent / "benchmark_results.json"
    out_file.write_text(json.dumps(metrics, indent=2))
    print(f"Saved results to {out_file}")


if __name__ == "__main__":
    run_benchmark()
