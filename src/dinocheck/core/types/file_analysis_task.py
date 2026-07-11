"""File analysis task type for planned per-file analysis work."""

from dataclasses import dataclass

from dinocheck.core.types.file_context import FileContext
from dinocheck.core.types.rule import Rule


@dataclass
class FileAnalysisTask:
    """A pending analysis for one file: the file, its triggered rules, and cache keys."""

    file_ctx: FileContext
    rules: list[Rule]
    file_hash: str
    rules_hash: str
