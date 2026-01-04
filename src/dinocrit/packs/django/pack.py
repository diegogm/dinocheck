"""Django framework pack."""

from pathlib import Path

from dinocrit.core.interfaces import Pack
from dinocrit.core.types import Rule
from dinocrit.packs.loader import load_rules_from_directory


class DjangoPack(Pack):
    """Official Django framework pack.

    Provides Django and Django REST Framework best practices and common issue detection.
    These rules are designed to guide LLM coding assistants in vibe coding workflows.

    Rules are loaded from YAML files in the rules/ directory:
    - orm/: ORM and performance rules
    - transactions/: Transaction and consistency rules
    - security/: Security and authorization rules
    - drf/: Django REST Framework rules
    - migrations/: Database migration rules
    - testing/: Testing best practices
    """

    def __init__(self) -> None:
        rules_dir = Path(__file__).parent / "rules"
        self._rules = load_rules_from_directory(rules_dir)

    @property
    def name(self) -> str:
        return "django"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def rules(self) -> list[Rule]:
        return self._rules
