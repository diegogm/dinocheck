"""Analysis result type."""

from dataclasses import dataclass
from typing import Any

from dinocrit.core.types.issue import Issue


@dataclass
class AnalysisResult:
    """Result of a complete analysis run."""

    issues: list[Issue]
    score: int
    gate_passed: bool
    fail_reasons: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "issues": [i.to_dict() for i in self.issues],
            "summary": {
                "score": self.score,
                "gate": "pass" if self.gate_passed else "fail",
                "fail_reasons": self.fail_reasons,
                "counts": self._count_by_level(),
            },
            "meta": self.meta,
        }

    def _count_by_level(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            level = str(issue.level)
            counts[level] = counts.get(level, 0) + 1
        return counts
