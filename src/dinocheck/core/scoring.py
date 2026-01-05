"""Scoring logic for Dinocheck."""

from dinocheck.core.types import Issue, IssueLevel

# Weight for each issue level (higher = more severe)
LEVEL_WEIGHTS = {
    IssueLevel.BLOCKER: 25,
    IssueLevel.CRITICAL: 15,
    IssueLevel.MAJOR: 8,
    IssueLevel.MINOR: 3,
    IssueLevel.INFO: 0,
}


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


class ScoreCalculator:
    """Calculator for quality scores."""

    def calculate(self, issues: list[Issue]) -> int:
        """Calculate quality score for issues."""
        return calculate_score(issues)

    def get_summary(self, issues: list[Issue]) -> dict[str, object]:
        """Get a summary of issues and scoring."""
        score = self.calculate(issues)

        counts: dict[str, int] = {}
        for issue in issues:
            level = issue.level.value
            counts[level] = counts.get(level, 0) + 1

        return {
            "score": score,
            "max_score": 100,
            "counts": counts,
            "total_issues": len(issues),
        }
