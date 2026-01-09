"""LiteLLM-based provider for unified LLM access."""

from __future__ import annotations

import asyncio
import warnings

import litellm
from pydantic import BaseModel

from dinocheck.core.interfaces import LLMProvider

# Suppress LiteLLM debug info messages
litellm.suppress_debug_info = True

# Suppress Pydantic serialization warnings from LiteLLM's internal models
# These warnings occur because LiteLLM's Message/Choices types don't match
# expected field counts during serialization (harmless but noisy)
warnings.filterwarnings(
    "ignore",
    message=".*PydanticSerializationUnexpectedValue.*",
    category=UserWarning,
    module="pydantic.*",
)


class LiteLLMProvider(LLMProvider):
    """
    Unified LLM provider using LiteLLM.

    Supports 100+ providers including:
    - OpenAI: gpt-4o, gpt-4o-mini
    - Anthropic: claude-3-5-sonnet, claude-3-opus
    - Ollama: ollama/llama3, ollama/mistral
    - Azure, Bedrock, Vertex AI, etc.

    See: https://docs.litellm.ai/docs/providers
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        max_concurrent: int = 4,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._max_concurrent = max_concurrent

    @property
    def max_concurrent(self) -> int:
        """Maximum concurrent LLM requests."""
        return self._max_concurrent

    def complete_structured_sync(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        """Complete a prompt with structured output (synchronous version).

        This method is thread-safe and designed for use with ThreadPoolExecutor.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            # Build kwargs, only include optional params if provided
            kwargs: dict[str, object] = {
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
            # Only add optional params if provided (some models don't support them)
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            if temperature is not None:
                kwargs["temperature"] = temperature
            if self.base_url is not None:
                kwargs["base_url"] = self.base_url
            if self.api_key is not None:
                kwargs["api_key"] = self.api_key

            # LiteLLM synchronous completion
            response = litellm.completion(**kwargs)

            # Validate response structure
            if not response.choices:
                raise RuntimeError("LLM returned no choices")
            choice = response.choices[0]
            if not choice.message or not choice.message.content:
                raise RuntimeError("LLM returned empty message content")
            content = choice.message.content

            # Parse response into Pydantic model
            result = response_schema.model_validate_json(content)

            return result

        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}") from e

    async def complete_structured(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        """Complete a prompt with structured output (async).

        Runs the sync version in a thread to avoid blocking the event loop.
        """
        return await asyncio.to_thread(
            self.complete_structured_sync,
            prompt,
            response_schema,
            system,
            max_tokens,
            temperature,
        )

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        try:
            result: int = litellm.token_counter(model=self.model, text=text)
            return result
        except Exception:
            # Fallback: rough estimate of 4 chars per token
            return len(text) // 4
