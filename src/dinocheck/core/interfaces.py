"""Abstract base classes for Dinocheck components."""

import fnmatch
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
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

    @staticmethod
    def matches_file_pattern(path: Path, pattern: str) -> bool:
        """Match a path against a rule file pattern.

        fnmatch treats `**/` as requiring at least one directory, so
        `**/Dockerfile` would never match a root-level `Dockerfile`.
        Rule patterns mean "at any depth", so `**/x` also matches bare `x`.
        """
        path_str = path.as_posix()
        if fnmatch.fnmatch(path_str, pattern):
            return True
        return pattern.startswith("**/") and fnmatch.fnmatch(path_str, pattern[3:])

    def is_candidate_file(self, path: Path) -> bool:
        """Check whether any rule could apply to this path (patterns only).

        Used during discovery to decide which files are worth reading;
        content patterns are evaluated later in get_rules_for_file.
        """
        for rule in self.rules:
            if not rule.triggers.file_patterns:
                return True
            if any(self.matches_file_pattern(path, p) for p in rule.triggers.file_patterns):
                return True
        return False

    def get_rules_for_file(self, path: Path, content: str) -> list[Rule]:
        """Get applicable rules for a specific file."""
        applicable = []
        for rule in self.rules:
            # Check file patterns
            if rule.triggers.file_patterns:
                matched = any(
                    self.matches_file_pattern(path, pattern)
                    for pattern in rule.triggers.file_patterns
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
    def discover(
        self,
        paths: list[Path],
        diff_only: bool = True,
        is_candidate: Callable[[Path], bool] | None = None,
    ) -> Iterator[FileContext]:
        """Discover files to analyze.

        is_candidate pre-filters walked/changed files by path (e.g. against
        the enabled rule packs' file patterns) before reading their content.
        Explicitly given file paths bypass the filter - the user asked for them.
        """
        ...

    @abstractmethod
    def get_diff_hunks(self, path: Path) -> list[Any]:
        """Get diff hunks for a file."""
        ...
