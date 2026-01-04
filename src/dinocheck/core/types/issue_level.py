"""Issue severity level enum."""

from enum import Enum


class IssueLevel(str, Enum):
    """Severity level for issues."""

    BLOCKER = "blocker"  # Critical issue, must be fixed
    CRITICAL = "critical"  # High priority issue
    MAJOR = "major"  # Important issue to address
    MINOR = "minor"  # Low priority suggestion
    INFO = "info"  # Informational only

    def __str__(self) -> str:
        return self.value
