"""Abstract base classes for Dinocheck components."""

import asyncio
import fnmatch
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from dinocheck.core.types import AnalysisResult, CacheStats, FileContext, Issue, Rule


class Analyzer(ABC):
    """Base class for deterministic analyzers (ruff, mypy, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Analyzer name."""
        ...

    @abstractmethod
    def analyze(self, paths: list[Path], config: dict[str, Any]) -> Iterator[Issue]:
        """Run analysis on paths and yield issues."""
        ...


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


class LLMProvider(ABC):
    """Abstract LLM provider interface with structured outputs."""

    @property
    def max_concurrent(self) -> int:
        """Maximum concurrent requests (for ThreadPoolExecutor)."""
        return 4

    @abstractmethod
    def complete_structured_sync(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        """Complete a prompt with structured output (synchronous, thread-safe)."""
        ...

    async def complete_structured(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        """Complete a prompt with structured output (async).

        Default implementation runs sync version in a thread.
        """
        return await asyncio.to_thread(
            self.complete_structured_sync,
            prompt,
            response_schema,
            system,
            max_tokens,
            temperature,
        )

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        ...


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
    """Cache interface for analysis results."""

    @abstractmethod
    def get(self, file_hash: str, pack_version: str, rules_hash: str) -> list[Issue] | None:
        """Get cached issues for a file."""
        ...

    @abstractmethod
    def put(self, file_hash: str, pack_version: str, rules_hash: str, issues: list[Issue]) -> None:
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
