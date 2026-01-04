"""Diff hunk type for git diffs."""

from dataclasses import dataclass


@dataclass
class DiffHunk:
    """A diff hunk from git."""

    start_line: int
    end_line: int
    content: str
    header: str = ""
