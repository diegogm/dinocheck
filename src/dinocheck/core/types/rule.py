"""Rule type for code quality rules."""

import hashlib
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

    @property
    def fingerprint(self) -> str:
        """Content-addressed identity for cache keying.

        Includes everything the analyzer sees, so editing a rule's text
        (checklist, fix, examples, severity) invalidates cached results
        produced under the old wording - not just renaming its ID.
        """
        examples = self.examples or {}
        content = "\x1f".join(
            [
                self.id,
                self.level.value,
                self.description,
                "\x1e".join(self.checklist),
                self.fix,
                examples.get("bad", ""),
                examples.get("good", ""),
            ]
        )
        return f"{self.id}:{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> "Rule":
        """Create a Rule from YAML data."""
        level_raw = data.get("level", "info")
        level_str = str(level_raw).upper() if level_raw else "INFO"
        level = IssueLevel[level_str] if level_str in IssueLevel.__members__ else IssueLevel.INFO

        triggers_data = data.get("triggers")
        triggers_dict = triggers_data if isinstance(triggers_data, dict) else {}
        triggers = RuleTrigger(
            file_patterns=triggers_dict.get("file_patterns", []),
            code_patterns=triggers_dict.get("code_patterns", []),
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
