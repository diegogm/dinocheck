"""Cache statistics type."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CacheStats:
    """Statistics about the analysis cache."""

    entries: int
    size_bytes: int
    oldest_entry: str | None
    newest_entry: str | None


@dataclass(frozen=True)
class CostSummary:
    """Summary of LLM costs over a period."""

    total_calls: int
    total_tokens: int
    total_cost: float
    total_issues: int
    avg_cost_per_call: float
