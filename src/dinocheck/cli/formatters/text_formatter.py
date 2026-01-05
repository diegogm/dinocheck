"""Text formatter for human-readable colored output."""

from io import StringIO
from typing import ClassVar

from rich.console import Console
from rich.text import Text

from dinocheck.core.interfaces import Formatter
from dinocheck.core.types import AnalysisResult, Issue


class TextFormatter(Formatter):
    """Human-readable text output with colors."""

    # Visual elements (ASCII for terminal compatibility)
    SEPARATOR = "-" * 60
    ISSUE_SEPARATOR = "-" * 40

    # Colors by level
    LEVEL_COLORS: ClassVar[dict[str, str]] = {
        "blocker": "bright_red",
        "critical": "red",
        "major": "yellow",
        "minor": "cyan",
        "info": "blue",
    }

    @property
    def name(self) -> str:
        return "text"

    def format(self, result: AnalysisResult) -> str:
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=True, width=500)

        # Header
        header_text = Text()
        header_text.append("✓", style="bold cyan")
        header_text.append(f" Analysis Complete - Score: {result.score}/100")

        console.print()
        console.print(self.SEPARATOR, style="dim")
        console.print(header_text)
        console.print(self.SEPARATOR, style="dim")

        # Issues by file
        if result.issues:
            console.print(f"\nIssues ({len(result.issues)}):", style="bold")

            issues_by_file: dict[str, list[Issue]] = {}
            for issue in result.issues:
                path = str(issue.location.path)
                if path not in issues_by_file:
                    issues_by_file[path] = []
                issues_by_file[path].append(issue)

            for path, issues in issues_by_file.items():
                console.print()
                console.print(self.SEPARATOR, style="dim")
                console.print(f" {path}", style="bold cyan")
                console.print(self.SEPARATOR, style="dim")

                for i, issue in enumerate(issues):
                    if i > 0:
                        console.print(f"\n  {self.ISSUE_SEPARATOR}", style="dim")

                    # Issue header with level and title
                    level = issue.level.value
                    color = self.LEVEL_COLORS.get(level, "white")

                    header = Text()
                    header.append(f"\n  [{level.upper()}]", style=f"bold {color}")
                    header.append(f" {issue.title}")
                    console.print(header)

                    console.print(f"     Rule: {issue.rule_id}", style="dim")

                    # Why this is an issue
                    console.print("\n     Why: ", style="bold", end="")
                    console.print(issue.why)

                    # Actions to fix
                    if issue.do:
                        console.print("\n     Actions:", style="bold green")
                        for action in issue.do:
                            console.print(f"       • {action}", style="green")

        else:
            console.print("\n✓ No issues found!", style="bold green")

        # Meta footer (write directly to avoid Rich word wrapping)
        cost_usd = result.meta.get("cost_usd", 0.0)
        files = result.meta.get("files_analyzed", 0)
        cached = result.meta.get("cache_hits", 0)
        duration = result.meta.get("duration_ms", 0)

        output = buffer.getvalue()
        meta = f"\nChecked {files} files ({cached} cached) in {duration}ms for ${cost_usd:.3f}\n"
        return output + meta
