"""Completion result type returned by LLM providers."""

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class CompletionResult:
    """A structured completion plus usage metadata reported by the provider.

    Token counts and cost are None when the provider does not report them;
    callers fall back to estimates in that case.
    """

    data: BaseModel
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
