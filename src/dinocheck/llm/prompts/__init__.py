"""LLM prompt templates for Dinocheck."""

from dinocheck.llm.prompts.brief import BriefBuilder
from dinocheck.llm.prompts.critic import CriticPromptBuilder

__all__ = ["BriefBuilder", "CriticPromptBuilder"]
