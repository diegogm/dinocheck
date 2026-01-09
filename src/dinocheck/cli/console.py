"""Console utilities for colored output using Rich."""

import os
import sys
from typing import ClassVar

from rich.console import Console
from rich.table import Table
from rich.text import Text


def _should_use_color() -> bool:
    """Determine if color output should be enabled.

    Respects NO_COLOR env var and checks if output is a real terminal.
    """
    # Respect NO_COLOR standard (https://no-color.org/)
    if os.environ.get("NO_COLOR"):
        return False
    # Force color if FORCE_COLOR is set
    if os.environ.get("FORCE_COLOR"):
        return True
    # Check if stdout is a real terminal
    return sys.stdout.isatty()


class DinoConsole:
    """Centralized console output with Rich styling."""

    # Shared console instances (lazy initialization)
    _stdout: ClassVar[Console | None] = None
    _stderr: ClassVar[Console | None] = None

    @classmethod
    def _get_stdout(cls) -> Console:
        """Get or create stdout console."""
        if cls._stdout is None:
            use_color = _should_use_color()
            cls._stdout = Console(force_terminal=use_color, no_color=not use_color)
        return cls._stdout

    @classmethod
    def _get_stderr(cls) -> Console:
        """Get or create stderr console."""
        if cls._stderr is None:
            use_color = _should_use_color()
            cls._stderr = Console(stderr=True, force_terminal=use_color, no_color=not use_color)
        return cls._stderr

    # Style constants
    SUCCESS = "bold green"
    ERROR = "bold red"
    WARNING = "bold yellow"
    INFO = "bold blue"
    DIM = "dim"
    HEADER = "bold cyan"

    @classmethod
    def print(cls, message: str = "", style: str | None = None, err: bool = False) -> None:
        """Print a message with optional styling."""
        console = cls._get_stderr() if err else cls._get_stdout()
        console.print(message, style=style)

    @classmethod
    def success(cls, message: str, err: bool = False) -> None:
        """Print a success message."""
        text = Text()
        text.append("✓ ", style=cls.SUCCESS)
        text.append(message)
        console = cls._get_stderr() if err else cls._get_stdout()
        console.print(text)

    @classmethod
    def error(cls, message: str) -> None:
        """Print an error message to stderr."""
        text = Text()
        text.append("✗ ", style=cls.ERROR)
        text.append(message, style=cls.ERROR)
        cls._get_stderr().print(text)

    @classmethod
    def warning(cls, message: str, err: bool = False) -> None:
        """Print a warning message."""
        text = Text()
        text.append("⚠ ", style=cls.WARNING)
        text.append(message)
        console = cls._get_stderr() if err else cls._get_stdout()
        console.print(text)

    @classmethod
    def info(cls, message: str, err: bool = False) -> None:
        """Print an info message."""
        text = Text()
        text.append("(i) ", style=cls.INFO)
        text.append(message)
        console = cls._get_stderr() if err else cls._get_stdout()
        console.print(text)

    @classmethod
    def header(cls, title: str, err: bool = False) -> None:
        """Print a section header."""
        console = cls._get_stderr() if err else cls._get_stdout()
        console.print()
        console.print(title, style=cls.HEADER)
        console.print("─" * len(title), style=cls.DIM)

    @classmethod
    def step(cls, step: str, details: str, err: bool = True) -> None:
        """Print a progress step."""
        text = Text()
        text.append(f"[{step}] ", style=cls.INFO)
        text.append(details, style=cls.DIM)
        console = cls._get_stderr() if err else cls._get_stdout()
        console.print(text)

    @classmethod
    def file_status(cls, path: str, rules: int, status: str, err: bool = True) -> None:
        """Print file analysis status.

        Args:
            path: File path
            rules: Number of applicable rules
            status: One of 'skip', 'cache', 'analyze'
        """
        text = Text()

        # Status indicator and color
        if status == "skip":
            text.append("  ○ ", style="dim")
            text.append(path, style="dim")
            text.append(" → 0 rules, skipped", style="dim")
        elif status == "cache":
            text.append("  ◉ ", style="green")
            text.append(path, style="")
            text.append(f" → {rules} rules, ", style="dim")
            text.append("cached", style="green")
        elif status == "analyze":
            text.append("  ◎ ", style="yellow")
            text.append(path, style="")
            text.append(f" → {rules} rules, ", style="dim")
            text.append("analyzing", style="yellow")

        console = cls._get_stderr() if err else cls._get_stdout()
        console.print(text)

    @classmethod
    def banner(cls, title: str, err: bool = False) -> None:
        """Print a banner with separators."""
        console = cls._get_stderr() if err else cls._get_stdout()
        line = "═" * 60
        console.print(line, style=cls.DIM)
        console.print(f" {title}", style="bold")
        console.print(line, style=cls.DIM)

    @classmethod
    def status_line(cls, label: str, value: str, style: str | None = None) -> None:
        """Print a labeled status line."""
        text = Text()
        text.append(f"{label}: ", style=cls.DIM)
        text.append(value, style=style)
        cls._get_stdout().print(text)

    @classmethod
    def table(
        cls,
        title: str | None = None,
        columns: list[tuple[str, str]] | None = None,
    ) -> Table:
        """Create a styled table.

        Args:
            title: Optional table title
            columns: List of (name, style) tuples for columns

        Returns:
            Rich Table instance
        """
        table = Table(
            title=title,
            show_header=True,
            header_style="bold",
            border_style="dim",
            title_style="bold cyan",
        )
        if columns:
            for name, style in columns:
                table.add_column(name, style=style)
        return table

    @classmethod
    def print_table(cls, table: Table) -> None:
        """Print a table to stdout."""
        cls._get_stdout().print(table)

    @classmethod
    def rule(cls, title: str = "", style: str = "dim") -> None:
        """Print a horizontal rule with optional title."""
        cls._get_stdout().rule(title, style=style)


# Convenience aliases
console = DinoConsole()
