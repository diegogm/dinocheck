"""File context type for files being analyzed."""

from dataclasses import dataclass, field
from pathlib import Path

from dinocheck.core.types.diff_hunk import DiffHunk


@dataclass
class FileContext:
    """Context for a file being analyzed."""

    path: Path
    content: str
    diff_hunks: list[DiffHunk] = field(default_factory=list)
    is_new: bool = False
