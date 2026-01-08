"""Rule type for code quality rules."""

from dataclasses import dataclass, field
from typing import Any

from dinocheck.core.types.issue_level import IssueLevel
from dinocheck.core.types.rule_trigger import RuleTrigger


@dataclass
class Rule:
    """A code quality rule definition.

    Rules can be defined in code (built-in packs) or as YAML files (custom rules).
    """

    id: str
    name: str
    level: IssueLevel
    category: str
    description: str
    checklist: list[str]
    fix: str  # Human guidance for fixing
    tags: list[str] = field(default_factory=list)
    triggers: RuleTrigger = field(default_factory=RuleTrigger)
    examples: dict[str, str] | None = None  # {"bad": ..., "good": ...}

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> "Rule":
        """Create a Rule from YAML data."""
        level_str = data.get("level", "info").upper()
        level = IssueLevel[level_str] if level_str in IssueLevel.__members__ else IssueLevel.INFO

        triggers = RuleTrigger(
            file_patterns=data.get("triggers", {}).get("file_patterns", []),
            code_patterns=data.get("triggers", {}).get("code_patterns", []),
        )

        return cls(
            id=data["id"],
            name=data["name"],
            level=level,
            category=data.get("category", "general"),
            description=data.get("description", ""),
            checklist=data.get("checklist", []),
            fix=data.get("fix", ""),
            tags=data.get("tags", []),
            triggers=triggers,
            examples=data.get("examples"),
        )
