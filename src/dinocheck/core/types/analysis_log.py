"""Analysis run log entry type."""

from dataclasses import dataclass


@dataclass
class AnalysisLog:
    """Log entry for an analysis run submitted via `dino report`."""

    id: str
    timestamp: str
    analyzer: str
    pack: str
    files: list[str]
    duration_ms: int
    issues_found: int
