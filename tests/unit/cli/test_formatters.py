"""Tests for output formatters."""

import json
import re
from pathlib import Path

import pytest

from dinocheck.cli.formatters import get_formatter
from dinocheck.cli.formatters.json_formatter import JSONFormatter
from dinocheck.cli.formatters.jsonl_formatter import JSONLFormatter
from dinocheck.cli.formatters.text_formatter import TextFormatter
from dinocheck.core.types import AnalysisResult, Issue, IssueLevel, Location


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


@pytest.fixture
def sample_result():
    """Sample analysis result for testing."""
    return AnalysisResult(
        issues=[
            Issue(
                rule_id="python/bare-except",
                level=IssueLevel.MAJOR,
                location=Location(Path("test.py"), 10, 12),
                title="Bare except clause",
                why="Catches all exceptions including KeyboardInterrupt",
                do=["Specify exception type"],
                pack="python",
                source="llm",
                confidence=0.95,
            ),
            Issue(
                rule_id="django/n-plus-one",
                level=IssueLevel.CRITICAL,
                location=Location(Path("views.py"), 25, 30),
                title="N+1 query detected",
                why="Loop causes multiple queries",
                do=["Use select_related()", "Add prefetch_related()"],
                pack="django",
                source="llm",
                confidence=0.88,
            ),
        ],
        score=75,
        meta={
            "files_analyzed": 5,
            "cache_hits": 2,
            "llm_calls": 3,
        },
    )


@pytest.fixture
def empty_result():
    """Empty analysis result."""
    return AnalysisResult(
        issues=[],
        score=100,
        meta={
            "files_analyzed": 3,
            "cache_hits": 3,
            "llm_calls": 0,
        },
    )


class TestTextFormatter:
    """Tests for TextFormatter."""

    def test_name(self):
        """Should return 'text' as formatter name."""
        formatter = TextFormatter()
        assert formatter.name == "text"

    def test_format_with_issues(self, sample_result):
        """Should format result with issues."""
        formatter = TextFormatter()
        output = formatter.format(sample_result)

        assert "75/100" in output
        assert "test.py" in output
        assert "views.py" in output
        assert "Bare except" in output
        assert "N+1 query" in output
        assert "python/bare-except" in output
        assert "Specify exception type" in output

    def test_format_no_issues(self, empty_result):
        """Should format result with no issues."""
        formatter = TextFormatter()
        output = formatter.format(empty_result)

        assert "100/100" in output
        assert "No issues found" in output

    def test_format_meta_info(self, sample_result):
        """Should include meta information."""
        formatter = TextFormatter()
        output = strip_ansi(formatter.format(sample_result))

        assert "Checked 5 files" in output
        assert "2 cached" in output


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_name(self):
        """Should return 'json' as formatter name."""
        formatter = JSONFormatter()
        assert formatter.name == "json"

    def test_format_valid_json(self, sample_result):
        """Should produce valid JSON."""
        formatter = JSONFormatter()
        output = formatter.format(sample_result)

        data = json.loads(output)
        assert isinstance(data, dict)

    def test_format_structure(self, sample_result):
        """Should have correct structure."""
        formatter = JSONFormatter()
        output = formatter.format(sample_result)

        data = json.loads(output)
        assert data["summary"]["score"] == 75
        assert len(data["issues"]) == 2

    def test_format_empty_result(self, empty_result):
        """Should format empty result."""
        formatter = JSONFormatter()
        output = formatter.format(empty_result)

        data = json.loads(output)
        assert data["summary"]["score"] == 100
        assert data["issues"] == []


class TestJSONLFormatter:
    """Tests for JSONLFormatter."""

    def test_name(self):
        """Should return 'jsonl' as formatter name."""
        formatter = JSONLFormatter()
        assert formatter.name == "jsonl"

    def test_format_lines(self, sample_result):
        """Should produce one JSON per line."""
        formatter = JSONLFormatter()
        output = formatter.format(sample_result)

        lines = output.strip().split("\n")
        assert len(lines) == 3  # 1 summary + 2 issues

        for line in lines:
            data = json.loads(line)
            assert "type" in data

    def test_format_summary_line(self, sample_result):
        """Should have summary as first line."""
        formatter = JSONLFormatter()
        output = formatter.format(sample_result)

        first_line = output.strip().split("\n")[0]
        data = json.loads(first_line)

        assert data["type"] == "summary"
        assert data["score"] == 75
        assert data["issues_count"] == 2

    def test_format_issue_lines(self, sample_result):
        """Should have issue details in subsequent lines."""
        formatter = JSONLFormatter()
        output = formatter.format(sample_result)

        lines = output.strip().split("\n")
        issue_line = json.loads(lines[1])

        assert issue_line["type"] == "issue"
        assert "rule_id" in issue_line
        assert "location" in issue_line

    def test_format_empty_result(self, empty_result):
        """Should only have summary line for empty result."""
        formatter = JSONLFormatter()
        output = formatter.format(empty_result)

        lines = output.strip().split("\n")
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["type"] == "summary"
        assert data["score"] == 100


class TestGetFormatter:
    """Tests for get_formatter factory."""

    def test_get_text(self):
        """Should return TextFormatter for 'text'."""
        formatter = get_formatter("text")
        assert isinstance(formatter, TextFormatter)

    def test_get_json(self):
        """Should return JSONFormatter for 'json'."""
        formatter = get_formatter("json")
        assert isinstance(formatter, JSONFormatter)

    def test_get_jsonl(self):
        """Should return JSONLFormatter for 'jsonl'."""
        formatter = get_formatter("jsonl")
        assert isinstance(formatter, JSONLFormatter)

    def test_get_unknown(self):
        """Should raise ValueError for unknown format."""
        with pytest.raises(ValueError, match="Unknown format"):
            get_formatter("xml")
