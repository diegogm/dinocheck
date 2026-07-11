"""Tests for the issue factory."""

from pathlib import Path

import pytest

from dinocheck.core.issue_factory import MAX_ISSUES_PER_FILE, IssueFactory
from dinocheck.core.types import FileContext, Issue, IssueLevel, Location
from dinocheck.llm.schemas import CriticIssue, CriticResponse, IssueLocation


@pytest.fixture
def factory():
    return IssueFactory()


@pytest.fixture
def file_ctx():
    return FileContext(
        path=Path("views.py"),
        content="def foo():\n    return 1\n\ndef bar():\n    return 2\n",
    )


def _critic_issue(rule_id="django/n-plus-one", level="major", start_line=1, title="An issue"):
    return CriticIssue(
        rule_id=rule_id,
        level=level,
        location=IssueLocation(start_line=start_line, end_line=start_line),
        title=title,
        why="Because",
        do=["Fix it"],
        confidence=0.9,
    )


class TestCreateIssues:
    """Tests for IssueFactory.create_issues."""

    def test_creates_issues_from_response(self, factory, file_ctx):
        response = CriticResponse(issues=[_critic_issue()])

        issues, warnings = factory.create_issues(response, file_ctx, "django")

        assert warnings == []
        assert len(issues) == 1
        issue = issues[0]
        assert issue.rule_id == "django/n-plus-one"
        assert issue.level == IssueLevel.MAJOR
        assert issue.location.path == file_ctx.path
        assert issue.pack == "django"
        assert issue.snippet is not None

    def test_invalid_level_is_reported_not_silent(self, factory, file_ctx):
        response = CriticResponse(issues=[_critic_issue(level="catastrophic")])

        issues, warnings = factory.create_issues(response, file_ctx, "django")

        assert issues == []
        assert len(warnings) == 1
        assert "catastrophic" in warnings[0]

    def test_source_is_configurable(self, factory, file_ctx):
        response = CriticResponse(issues=[_critic_issue()])

        issues, _ = factory.create_issues(response, file_ctx, "django", source="agent")

        assert issues[0].source == "agent"

    def test_unknown_rule_id_is_dropped_with_warning(self, factory, file_ctx):
        """Findings citing rules not in the brief are rejected (no invented rules)."""
        response = CriticResponse(issues=[_critic_issue(rule_id="made-up/rule")])

        issues, warnings = factory.create_issues(
            response, file_ctx, "django", allowed_rule_ids={"django/n-plus-one"}
        )

        assert issues == []
        assert len(warnings) == 1
        assert "made-up/rule" in warnings[0]

    def test_allowed_rule_id_passes(self, factory, file_ctx):
        response = CriticResponse(issues=[_critic_issue(rule_id="django/n-plus-one")])

        issues, warnings = factory.create_issues(
            response, file_ctx, "django", allowed_rule_ids={"django/n-plus-one"}
        )

        assert len(issues) == 1
        assert warnings == []

    def test_start_line_out_of_range_is_dropped(self, factory, file_ctx):
        """The fixture file has 5 lines; line 999 is a hallucination."""
        response = CriticResponse(issues=[_critic_issue(start_line=999)])

        issues, warnings = factory.create_issues(response, file_ctx, "django")

        assert issues == []
        assert len(warnings) == 1
        assert "out of range" in warnings[0]

    def test_overshot_end_line_is_clamped(self, factory, file_ctx):
        issue = _critic_issue(start_line=4)
        issue.location.end_line = 999
        response = CriticResponse(issues=[issue])

        issues, warnings = factory.create_issues(response, file_ctx, "django")

        assert warnings == []
        assert issues[0].location.end_line <= file_ctx.content.count("\n") + 1


def _issue(rule_id="a/rule", level=IssueLevel.MINOR, line=1, title="t", path="f.py"):
    return Issue(
        rule_id=rule_id,
        level=level,
        location=Location(Path(path), line),
        title=title,
        why="w",
        do=["d"],
        pack="test",
    )


class TestPostProcessing:
    """Tests for filtering, dedupe, and limits."""

    def test_deduplicate(self, factory):
        issues = [_issue(), _issue(), _issue(title="other")]

        assert len(factory.deduplicate(issues)) == 2

    def test_filter_disabled(self, factory):
        issues = [_issue(rule_id="a/one"), _issue(rule_id="a/two")]

        result = factory.filter_disabled(issues, ["a/one"])

        assert [i.rule_id for i in result] == ["a/two"]

    def test_filter_rules(self, factory):
        issues = [_issue(rule_id="a/one"), _issue(rule_id="a/two")]

        result = factory.filter_rules(issues, ["one"])

        assert [i.rule_id for i in result] == ["a/one"]

    def test_limit_per_file_keeps_most_severe(self, factory):
        issues = [
            _issue(line=i, title=f"minor {i}", level=IssueLevel.MINOR)
            for i in range(MAX_ISSUES_PER_FILE + 5)
        ]
        issues.append(_issue(line=99, title="blocker", level=IssueLevel.BLOCKER))

        result = factory.limit_per_file(issues)

        assert len(result) == MAX_ISSUES_PER_FILE
        assert result[0].level == IssueLevel.BLOCKER

    def test_finalize_pipeline(self, factory):
        issues = [
            _issue(rule_id="a/keep", title="kept"),
            _issue(rule_id="a/keep", title="kept"),  # duplicate
            _issue(rule_id="a/disabled", title="disabled"),
        ]

        result = factory.finalize(issues, disabled_rules=["a/disabled"])

        assert len(result) == 1
        assert result[0].title == "kept"
