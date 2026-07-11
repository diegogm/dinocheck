"""Cache statistics type."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CacheStats:
    """Statistics about the analysis cache."""

    entries: int
    size_bytes: int
    oldest_entry: str | None
    newest_entry: str | None
