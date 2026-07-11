"""Analysis plan type produced by the planner."""

from dataclasses import dataclass, field

from dinocheck.core.types.file_analysis_task import FileAnalysisTask
from dinocheck.core.types.issue import Issue


@dataclass
class AnalysisPlan:
    """The deterministic half of an analysis run.

    Contains everything needed to execute the semantic analysis: pending
    per-file tasks with their triggered rules, plus results already
    resolved from cache.
    """

    pack_name: str
    tasks: list[FileAnalysisTask] = field(default_factory=list)
    cached_issues: list[Issue] = field(default_factory=list)
    files_total: int = 0
    cache_hits: int = 0
    skipped_no_rules: int = 0
