"""Source code location type."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Location:
    """Source code location."""

    path: Path
    start_line: int
    end_line: int | None = None
    start_col: int | None = None
    end_col: int | None = None

    def __str__(self) -> str:
        s = f"{self.path}:{self.start_line}"
        if self.end_line and self.end_line != self.start_line:
            s += f"-{self.end_line}"
        return s

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_col": self.start_col,
            "end_col": self.end_col,
        }
