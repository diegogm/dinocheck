"""Issue type for detected code quality issues."""

import hashlib
from dataclasses import dataclass, field
from typing import Any

from dinocheck.core.types.issue_level import IssueLevel
from dinocheck.core.types.location import Location


@dataclass
class Issue:
    """A detected code quality issue."""

    rule_id: str
    level: IssueLevel
    location: Location
    title: str
    why: str
    do: list[str]
    pack: str
    source: str = "llm"  # "llm" for LLM-detected issues
    confidence: float = 1.0
    tags: list[str] = field(default_factory=list)
    snippet: str | None = None  # Code snippet around the issue
    context: str | None = None  # Function/class name containing the issue

    @property
    def issue_id(self) -> str:
        """Content-addressed ID for deduplication."""
        content = f"{self.rule_id}:{self.location}:{self.title}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "rule_id": self.rule_id,
            "level": str(self.level),
            "location": self.location.to_dict(),
            "title": self.title,
            "why": self.why,
            "do": self.do,
            "pack": self.pack,
            "confidence": self.confidence,
            "tags": self.tags,
            "snippet": self.snippet,
            "context": self.context,
        }
