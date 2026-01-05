"""Tests for scoring logic."""

from pathlib import Path

from dinocheck.core.scoring import ScoreCalculator, calculate_score
from dinocheck.core.types import Issue, IssueLevel, Location


def make_issue(level: IssueLevel) -> Issue:
    """Create a test issue with given level."""
    return Issue(
        rule_id=f"test/{level.value}",
        level=level,
        location=Location(Path("test.py"), 1),
        title=f"Test {level.value} issue",
        why="Test reason",
        do=["Fix it"],
        pack="test",
        source="test",
    )


class TestCalculateScore:
    """Tests for calculate_score function."""

    def test_perfect_score_no_issues(self):
        """No issues should result in perfect score."""
        assert calculate_score([]) == 100

    def test_score_with_blocker(self):
        """Blocker should have highest penalty."""
        issues = [make_issue(IssueLevel.BLOCKER)]
        score = calculate_score(issues)
        assert score == 75  # 100 - 25

    def test_score_with_critical(self):
        """Critical should have high penalty."""
        issues = [make_issue(IssueLevel.CRITICAL)]
        score = calculate_score(issues)
        assert score == 85  # 100 - 15

    def test_score_with_major(self):
        """Major should have medium penalty."""
        issues = [make_issue(IssueLevel.MAJOR)]
        score = calculate_score(issues)
        assert score == 92  # 100 - 8

    def test_score_with_minor(self):
        """Minor should have low penalty."""
        issues = [make_issue(IssueLevel.MINOR)]
        score = calculate_score(issues)
        assert score == 97  # 100 - 3

    def test_score_with_info(self):
        """Info should have no penalty."""
        issues = [make_issue(IssueLevel.INFO)]
        score = calculate_score(issues)
        assert score == 100

    def test_score_multiple_issues(self):
        """Multiple issues should accumulate penalties."""
        issues = [
            make_issue(IssueLevel.MAJOR),
            make_issue(IssueLevel.MAJOR),
            make_issue(IssueLevel.MINOR),
        ]
        score = calculate_score(issues)
        assert score == 81  # 100 - 8 - 8 - 3

    def test_score_floor_at_zero(self):
        """Score should not go below 0."""
        issues = [make_issue(IssueLevel.BLOCKER) for _ in range(10)]
        score = calculate_score(issues)
        assert score == 0


class TestScoreCalculator:
    """Tests for ScoreCalculator class."""

    def test_get_summary(self, sample_issues):
        """Should return complete summary."""
        calculator = ScoreCalculator()
        summary = calculator.get_summary(sample_issues)

        assert "score" in summary
        assert "counts" in summary
        assert summary["total_issues"] == 3

    def test_counts_by_level(self, sample_issues):
        """Should count issues by level correctly."""
        calculator = ScoreCalculator()
        summary = calculator.get_summary(sample_issues)

        assert summary["counts"]["major"] == 2
        assert summary["counts"]["blocker"] == 1
