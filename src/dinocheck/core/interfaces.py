"""Abstract base classes for Dinocheck components."""

import fnmatch
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from dinocheck.core.types import AnalysisResult, CacheStats, FileContext, Issue, Rule


class Pack(ABC):
    """Base class for rule packs."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Pack name (e.g., 'django', 'python')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Pack version."""
        ...

    @property
    @abstractmethod
    def rules(self) -> list[Rule]:
        """List of rules in this pack."""
        ...

    @property
    def triggers(self) -> dict[str, Any]:
        """Pack-level trigger configuration."""
        return {}

    def get_rules_for_file(self, path: Path, content: str) -> list[Rule]:
        """Get applicable rules for a specific file."""
        applicable = []
        for rule in self.rules:
            # Check file patterns
            if rule.triggers.file_patterns:
                matched = any(
                    fnmatch.fnmatch(str(path), pattern) for pattern in rule.triggers.file_patterns
                )
                if not matched:
                    continue

            # Check code patterns
            if rule.triggers.code_patterns:
                matched = any(
                    re.search(pattern, content) for pattern in rule.triggers.code_patterns
                )
                if not matched:
                    continue

            applicable.append(rule)

        return applicable


class Formatter(ABC):
    """Output formatter interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Formatter name."""
        ...

    @abstractmethod
    def format(self, result: AnalysisResult) -> str:
        """Format analysis result as string."""
        ...


class Cache(ABC):
    """Cache interface for analysis results.

    Results are keyed by file content, rule set, AND the analyzer that
    produced them, so results from different analyzers never collide.
    """

    @abstractmethod
    def get(self, file_hash: str, rules_hash: str, analyzer: str) -> list[Issue] | None:
        """Get cached issues for a file."""
        ...

    @abstractmethod
    def put(self, file_hash: str, rules_hash: str, analyzer: str, issues: list[Issue]) -> None:
        """Cache issues for a file."""
        ...

    @abstractmethod
    def clear(self, older_than_hours: int | None = None) -> int:
        """Clear cache entries, optionally older than a threshold."""
        ...

    @abstractmethod
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        ...


class WorkspaceScanner(ABC):
    """Scans workspace for files to analyze."""

    @abstractmethod
    def discover(self, paths: list[Path], diff_only: bool = True) -> Iterator[FileContext]:
        """Discover files to analyze."""
        ...

    @abstractmethod
    def get_diff_hunks(self, path: Path) -> list[Any]:
        """Get diff hunks for a file."""
        ...
