"""Scoring and gate logic for Dinocrit."""

from dinocrit.core.types import Issue, IssueLevel

# Weight for each issue level (higher = more severe)
LEVEL_WEIGHTS = {
    IssueLevel.BLOCKER: 25,
    IssueLevel.CRITICAL: 15,
    IssueLevel.MAJOR: 8,
    IssueLevel.MINOR: 3,
    IssueLevel.INFO: 0,
}

# Default gate policy: fail on blockers, criticals, and majors
DEFAULT_FAIL_LEVELS = [IssueLevel.BLOCKER, IssueLevel.CRITICAL, IssueLevel.MAJOR]
DEFAULT_SCORE_THRESHOLD = 70


def calculate_score(issues: list[Issue]) -> int:
    """
    Calculate quality score (0-100, higher is better).

    Score is calculated by subtracting penalty points for each issue
    based on severity level.
    """
    if not issues:
        return 100

    penalty = sum(LEVEL_WEIGHTS.get(issue.level, 0) for issue in issues)
    score = max(0, 100 - penalty)
    return score


def check_gate(
    issues: list[Issue],
    fail_levels: list[IssueLevel] | None = None,
    score_threshold: int | None = None,
) -> tuple[bool, list[str]]:
    """
    Check if issues pass the gate.

    Returns (passed, reasons) where reasons is a list of failure reasons.
    """
    if fail_levels is None:
        fail_levels = DEFAULT_FAIL_LEVELS
    if score_threshold is None:
        score_threshold = DEFAULT_SCORE_THRESHOLD

    reasons = []

    # Check fail levels
    for level in fail_levels:
        if isinstance(level, str):
            level = IssueLevel(level)
        count = sum(1 for i in issues if i.level == level)
        if count > 0:
            reasons.append(f"{count} {level.value} issue(s)")

    # Check score threshold
    score = calculate_score(issues)
    if score < score_threshold:
        reasons.append(f"Score {score} below threshold {score_threshold}")

    return (len(reasons) == 0, reasons)


class ScoreCalculator:
    """Calculator for quality scores and gate checks."""

    def __init__(
        self,
        fail_levels: list[IssueLevel] | None = None,
        score_threshold: int | None = None,
    ):
        self.fail_levels = fail_levels or DEFAULT_FAIL_LEVELS
        self.score_threshold = score_threshold or DEFAULT_SCORE_THRESHOLD

    def calculate(self, issues: list[Issue]) -> int:
        """Calculate quality score for issues."""
        return calculate_score(issues)

    def check_gate(self, issues: list[Issue]) -> tuple[bool, list[str]]:
        """Check if issues pass the gate."""
        return check_gate(issues, self.fail_levels, self.score_threshold)

    def get_summary(self, issues: list[Issue]) -> dict[str, object]:
        """Get a summary of issues and scoring."""
        score = self.calculate(issues)
        passed, reasons = self.check_gate(issues)

        counts: dict[str, int] = {}
        for issue in issues:
            level = issue.level.value
            counts[level] = counts.get(level, 0) + 1

        return {
            "score": score,
            "max_score": 100,
            "gate": "pass" if passed else "fail",
            "fail_reasons": reasons,
            "counts": counts,
            "total_issues": len(issues),
        }
