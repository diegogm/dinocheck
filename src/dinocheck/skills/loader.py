"""Loading of agent skill templates shipped as package data."""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"


class SkillTemplates:
    """Loads skill templates for supported coding agents."""

    AGENTS = ("claude", "codex", "gemini")

    @classmethod
    def get(cls, agent: str) -> str:
        """Return the SKILL.md content for an agent.

        Raises:
            ValueError: If the agent has no template.
        """
        if agent not in cls.AGENTS:
            raise ValueError(f"Unknown agent: {agent} (expected one of {', '.join(cls.AGENTS)})")
        template_path = TEMPLATES_DIR / f"{agent}.md"
        return template_path.read_text(encoding="utf-8")
