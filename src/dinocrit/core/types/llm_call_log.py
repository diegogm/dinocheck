"""LLM call log entry type."""

from dataclasses import dataclass


@dataclass
class LLMCallLog:
    """Log entry for an LLM call."""

    id: str
    timestamp: str
    model: str
    pack: str
    files: list[str]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    duration_ms: int
    issues_found: int
    cached: bool = False
