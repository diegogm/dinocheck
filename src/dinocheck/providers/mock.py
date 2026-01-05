"""Mock provider for testing."""

from typing import Any

from pydantic import BaseModel

from dinocheck.core.interfaces import LLMProvider


class MockProvider(LLMProvider):
    """Mock LLM provider for testing with deterministic responses."""

    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses = responses or {}
        self.calls: list[dict[str, Any]] = []

    @property
    def max_concurrent(self) -> int:
        """Maximum concurrent requests."""
        return 4

    def complete_structured_sync(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        """Return mock response based on prompt content (synchronous)."""
        self.calls.append(
            {
                "prompt": prompt,
                "schema": response_schema,
                "system": system,
            }
        )

        # Check for matching response
        for key, response in self.responses.items():
            if key in prompt:
                if isinstance(response, dict):
                    return response_schema.model_validate(response)
                # Already validated, return as-is
                if isinstance(response, BaseModel):
                    return response
                return response_schema.model_validate(response)

        # Return empty response - use model_construct to bypass validation
        # This works for any schema, not just ones with an 'issues' field
        return response_schema.model_construct()

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count."""
        return len(text) // 4
