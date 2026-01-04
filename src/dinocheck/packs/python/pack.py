"""Python language pack."""

from pathlib import Path

from dinocheck.core.interfaces import Pack
from dinocheck.core.types import Rule
from dinocheck.packs.loader import load_rules_from_directory


class PythonPack(Pack):
    """Base Python language pack.

    Provides general Python best practices and common issue detection.
    These rules are designed to guide LLM coding assistants in vibe coding workflows.

    Rules are loaded from YAML files in the rules/ directory.
    """

    def __init__(self) -> None:
        rules_dir = Path(__file__).parent / "rules"
        self._rules = load_rules_from_directory(rules_dir)

    @property
    def name(self) -> str:
        return "python"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def rules(self) -> list[Rule]:
        return self._rules
