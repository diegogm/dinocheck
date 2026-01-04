"""LLM providers for Dinocrit."""

from dinocrit.providers.litellm_provider import LiteLLMProvider
from dinocrit.providers.mock import MockProvider

__all__ = ["LiteLLMProvider", "MockProvider"]
