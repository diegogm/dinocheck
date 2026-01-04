"""LLM providers for Dinocrit."""

from dinocheck.providers.litellm_provider import LiteLLMProvider
from dinocheck.providers.mock import MockProvider

__all__ = ["LiteLLMProvider", "MockProvider"]
