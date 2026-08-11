"""Unit tests for individual agents."""

from gitpilot.agents import (
    code_reader,
    code_writer,
    issue_loader,
    planner,
    pr_opener,
    repair_agent,
    research_agent,
    reviewer,
)
from gitpilot.agents import (
    test_runner as agent_test_runner,
)
from gitpilot.agents import (
    test_writer as agent_test_writer,
)
from gitpilot.agents.code_writer import _parse_generated_files
from gitpilot.github.client import MockGitHubClient
from gitpilot.llm.base import LLMResponse
from gitpilot.llm.mock import MockLLMProvider


def test_issue_loader_agent():
    gh = MockGitHubClient()
    state = {"issue": {"number": 1}, "repository_url": "https://github.com/demo/calc", "execution_log": []}
    res = issue_loader(state, github_client=gh)
    assert res["issue"]["title"] is not None
    assert res["status"] == "running"


def test_code_reader_demo():
    state = {"repo_path": "", "issue": {"title": "divide error"}, "execution_log": []}
    res = code_reader(state)
    assert "calculator.py" in res["retrieved_files"]
    assert "divide" in res["code_context"]


def test_planner_agent():
    llm = MockLLMProvider()
    state = {
        "issue": {"title": "Divide zero crash", "body": "Crashes on zero"},
        "code_context": "def divide(a, b): return a / b",
        "execution_log": [],
    }
    res = planner(state, llm=llm)
    assert "plan" in res
    assert res["complexity"] in ("simple", "complex")
    assert res["plan"]["summary"] is not None


def test_planner_normalizes_object_wrapped_lists_from_local_models():
    class ObjectListLLM:
        def name(self):
            return "ollama:test"

        def generate(self, prompt, system=""):
            return LLMResponse(
                model="test",
                content='''{
                    "summary": "Add Storybook",
                    "root_cause": "Storybook is missing",
                    "files_to_modify": [{"path": "package.json"}],
                    "files_to_add": [{"file": ".storybook/main.js"}],
                    "implementation_steps": [{"step": "Install Storybook"}],
                    "test_strategy": [{"test_case": "Verify Storybook starts"}],
                    "risk_level": "low",
                    "complexity": "simple"
                }''',
            )

    result = planner(
        {"issue": {"title": "Add Storybook"}, "execution_log": []},
        llm=ObjectListLLM(),
    )

    assert result["plan"]["files_to_modify"] == ["package.json"]
    assert result["plan"]["files_to_add"] == [".storybook/main.js"]
    assert result["plan"]["implementation_steps"] == ["Install Storybook"]
    assert result["plan"]["test_strategy"] == ["Verify Storybook starts"]


def test_mock_plans_are_issue_specific():
    llm = MockLLMProvider()
    first = planner(
        {
            "issue": {"title": "Navbar disappears on mobile", "body": "At 480px"},
            "code_context": "// src/Navbar.tsx",
            "file_tree": "src/Navbar.tsx",
            "execution_log": [],
        },
        llm=llm,
    )
    second = planner(
        {
            "issue": {"title": "CSV export loses dates", "body": "Dates are blank"},
            "code_context": "# export_csv.py",
            "file_tree": "export_csv.py",
            "execution_log": [],
        },
        llm=llm,
    )
    assert first["plan"]["summary"] != second["plan"]["summary"]
    assert "navbar" in first["plan"]["summary"].lower()
    assert "csv" in second["plan"]["summary"].lower()


def test_research_agent():
    llm = MockLLMProvider()
    state = {"plan": {"summary": "fix divide"}, "code_context": "...", "execution_log": []}
    res = research_agent(state, llm=llm)
    assert "research_notes" in res


def test_code_writer_agent():
    llm = MockLLMProvider()
    state = {
        "plan": {"files_to_modify": ["calculator.py"]},
        "code_context": "...",
        "execution_log": [],
    }
    res = code_writer(state, llm=llm)
    assert "patch" in res


def test_code_writer_repairs_unescaped_code_backslashes():
    files = _parse_generated_files(
        r'{"files":[{"path":"config.js","content":"const pattern = /\.stories\.js$/;"}]}'
    )

    assert files == [
        {"path": "config.js", "content": r"const pattern = /\.stories\.js$/;"}
    ]


def test_test_writer_agent():
    llm = MockLLMProvider()
    state = {"plan": {"files_to_modify": ["calculator.py"]}, "patch": "...", "execution_log": []}
    res = agent_test_writer(state, llm=llm)
    assert "tests" in res


def test_test_runner_demo_agent():
    state = {"repo_path": "", "attempt_count": 0, "execution_log": []}
    res = agent_test_runner(state)
    assert res["test_results"]["passed"] is True
    assert res["attempt_count"] == 1


def test_reviewer():
    llm = MockLLMProvider()
    state = {
        "issue": {"title": "bug"},
        "plan": {"summary": "fix"},
        "patch": "def divide...",
        "test_results": {"passed": True},
        "execution_log": [],
    }
    res = reviewer(state, llm=llm)
    assert "review_feedback" in res
    assert "approved" in res["review_feedback"]


def test_repair_agent():
    llm = MockLLMProvider()
    state = {
        "attempt_count": 1,
        "patch": "broken code",
        "test_results": {"passed": False, "stderr": "SyntaxError"},
        "execution_log": [],
    }
    res = repair_agent(state, llm=llm)
    assert "patch" in res
    assert len(res["repair_history"]) == 1


def test_pr_opener_dry_run():
    gh = MockGitHubClient()
    state = {
        "issue": {"number": 1, "title": "bug"},
        "plan": {"summary": "fixed bug"},
        "repository_url": "https://github.com/demo/calc",
        "execution_log": [],
    }
    res = pr_opener(state, github_client=gh, dry_run=True)
    assert res["status"] == "success"
    assert "[DRY RUN]" in res["pr_url"]
