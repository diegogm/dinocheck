"""Rule trigger conditions type."""

from dataclasses import dataclass, field


@dataclass
class RuleTrigger:
    """Conditions that trigger LLM analysis for a rule."""

    file_patterns: list[str] = field(default_factory=list)  # glob patterns
    code_patterns: list[str] = field(default_factory=list)  # regex patterns
