"""LiteLLM-based provider for unified LLM access."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import litellm
from pydantic import BaseModel

from dinocheck.core.interfaces import LLMProvider

if TYPE_CHECKING:
    from dinocheck.core.cache import SQLiteCache

# Suppress LiteLLM debug info messages
litellm.suppress_debug_info = True


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
        cache_db: Path | None = None,
        max_concurrent: int = 4,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.cache_db = cache_db
        self._max_concurrent = max_concurrent
        self._cache: SQLiteCache | None = None

        # Set API key if provided
        if api_key:
            # LiteLLM reads from env, so we set it there
            if "anthropic" in model.lower() or "claude" in model.lower():
                os.environ["ANTHROPIC_API_KEY"] = api_key
            else:
                os.environ["OPENAI_API_KEY"] = api_key

    @property
    def max_concurrent(self) -> int:
        """Maximum concurrent LLM requests."""
        return self._max_concurrent

    def _get_cache(self) -> SQLiteCache | None:
        """Get or create cache instance (lazy initialization)."""
        if self.cache_db and self._cache is None:
            from dinocheck.core.cache import SQLiteCache

            self._cache = SQLiteCache(self.cache_db)
        return self._cache

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

        start_time = time.time()

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

            # LiteLLM synchronous completion
            response = litellm.completion(**kwargs)

            content = response.choices[0].message.content
            duration_ms = int((time.time() - start_time) * 1000)

            # Parse response into Pydantic model
            result = response_schema.model_validate_json(content)

            # Log the call if cache is available and usage metadata exists
            cache = self._get_cache()
            if cache and response.usage:
                # Get issue count from response if it has issues
                issues_found = 0
                if hasattr(result, "issues"):
                    issues_found = len(result.issues)

                cache.log_llm_call(
                    model=self.model,
                    pack="unknown",  # Will be set by caller
                    files=[],  # Will be set by caller
                    prompt_tokens=response.usage.prompt_tokens or 0,
                    completion_tokens=response.usage.completion_tokens or 0,
                    duration_ms=duration_ms,
                    issues_found=issues_found,
                )

            return result

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
