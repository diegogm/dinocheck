"""Integration tests for the agent-mode brief/report workflow."""

import json

import pytest
from typer.testing import CliRunner

from dinocheck.cli.main import app

runner = CliRunner()

VIEWS_CONTENT = """\
from .models import Book

def book_list(request):
    for b in Book.objects.all():
        print(b.author.name)
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A minimal project with a Django views file."""
    monkeypatch.chdir(tmp_path)
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "views.py").write_text(VIEWS_CONTENT)
    return tmp_path


class TestBriefCommand:
    """Tests for dino brief."""

    def test_brief_lists_files_and_rules(self, project):
        result = runner.invoke(app, ["brief", "app/views.py"])

        assert result.exit_code == 0
        assert "# Dinocheck Review Brief" in result.stdout
        assert "app/views.py" in result.stdout
        assert "Rules to evaluate" in result.stdout
        assert "dino report" in result.stdout

    def test_brief_writes_output_file(self, project):
        result = runner.invoke(app, ["brief", "app/views.py", "-o", "brief.md"])

        assert result.exit_code == 0
        brief_file = project / "brief.md"
        assert brief_file.exists()
        assert "app/views.py" in brief_file.read_text()

    def test_brief_does_not_embed_code_by_default(self, project):
        result = runner.invoke(app, ["brief", "app/views.py"])

        assert "book_list" not in result.stdout

    def test_brief_embed_code(self, project):
        result = runner.invoke(app, ["brief", "app/views.py", "--embed-code"])

        assert result.exit_code == 0
        assert "book_list" in result.stdout

    def test_brief_json_format(self, project):
        result = runner.invoke(app, ["brief", "app/views.py", "--format", "json", "--quiet"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["files"][0]["path"] == "app/views.py"
        assert len(data["files"][0]["rules"]) > 0
        assert data["summary"]["files_to_review"] == 1

    def test_brief_nothing_to_analyze(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        empty = tmp_path / "empty"
        empty.mkdir()

        result = runner.invoke(app, ["brief", "empty/"])

        assert result.exit_code == 0
        assert "Nothing to analyze" in result.stdout


class TestReportCommand:
    """Tests for dino report."""

    def _results(self, issues):
        return {"files": [{"path": "app/views.py", "issues": issues}]}

    def _issue(self, **overrides):
        issue = {
            "rule_id": "django/n-plus-one",
            "level": "major",
            "location": {"start_line": 4, "end_line": 5},
            "title": "N+1 query in book loop",
            "why": "Accessing b.author.name inside the loop issues one query per book.",
            "do": ["Use select_related('author')"],
            "confidence": 0.95,
        }
        issue.update(overrides)
        return issue

    def test_report_scores_and_formats_issues(self, project):
        results = project / "results.json"
        results.write_text(json.dumps(self._results([self._issue()])))

        result = runner.invoke(app, ["report", "results.json", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["summary"]["total_issues"] == 1
        assert data["summary"]["score"] < 100
        assert data["issues"][0]["rule_id"] == "django/n-plus-one"
        assert data["issues"][0]["source"] == "agent"

    def test_report_empty_issues_scores_100(self, project):
        results = project / "results.json"
        results.write_text(json.dumps(self._results([])))

        result = runner.invoke(app, ["report", "results.json", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["summary"]["score"] == 100

    def test_report_caches_results_for_next_brief(self, project):
        results = project / "results.json"
        results.write_text(json.dumps(self._results([self._issue()])))

        report_result = runner.invoke(app, ["report", "results.json"])
        assert report_result.exit_code == 0

        # The reported file is now cached: the next brief has nothing to review
        brief_result = runner.invoke(app, ["brief", "app/views.py"])
        assert brief_result.exit_code == 0
        assert "Nothing to analyze" in brief_result.stdout

    def test_report_invalid_json_shows_contract_errors(self, project):
        results = project / "results.json"
        results.write_text(json.dumps({"files": [{"issues": []}]}))  # missing path

        result = runner.invoke(app, ["report", "results.json"])

        assert result.exit_code == 2
        assert "output contract" in result.stderr
        assert "path" in result.stderr

    def test_report_invalid_level_is_warned_and_dropped(self, project):
        results = project / "results.json"
        results.write_text(json.dumps(self._results([self._issue(level="catastrophic")])))

        result = runner.invoke(
            app, ["report", "results.json", "--format", "json", "-o", "out.json", "--quiet"]
        )

        assert result.exit_code == 0
        assert "catastrophic" in result.stderr  # warning explains the dropped issue
        data = json.loads((project / "out.json").read_text())
        assert data["summary"]["total_issues"] == 0

    def test_report_missing_file_entry_is_ignored_with_warning(self, project):
        results = project / "results.json"
        results.write_text(
            json.dumps({"files": [{"path": "nonexistent.py", "issues": [self._issue()]}]})
        )

        result = runner.invoke(app, ["report", "results.json", "--format", "json"])

        assert result.exit_code == 0
        assert "nonexistent.py" in result.stderr

    def test_report_empty_files_list_is_an_error(self, project):
        results = project / "results.json"
        results.write_text(json.dumps({"files": []}))

        result = runner.invoke(app, ["report", "results.json"])

        assert result.exit_code == 2

    def test_report_missing_results_file(self, project):
        result = runner.invoke(app, ["report", "missing.json"])

        assert result.exit_code == 2
        assert "not found" in result.stderr


class TestCheckAgentModeGating:
    """Tests for dino check behavior in agent mode."""

    def test_check_in_agent_mode_points_to_brief(self, project):
        result = runner.invoke(app, ["check", "app/views.py"])

        assert result.exit_code == 2
        assert "dino brief" in result.stderr
        assert "dino report" in result.stderr
