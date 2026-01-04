"""Text formatter for human-readable colored output."""

from io import StringIO
from typing import ClassVar

from rich.console import Console
from rich.text import Text

from dinocrit.core.interfaces import Formatter
from dinocrit.core.types import AnalysisResult, Issue


class TextFormatter(Formatter):
    """Human-readable text output with colors."""

    # Visual elements
    SEPARATOR = "─" * 60
    ISSUE_SEPARATOR = "┈" * 40

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
        console = Console(file=buffer, force_terminal=True, width=100)

        # Header
        if result.gate_passed:
            gate_text = Text()
            gate_text.append("✓", style="bold green")
            gate_text.append(" Analysis Complete - Gate: ")
            gate_text.append("PASS", style="bold green")
            gate_text.append(f" - Score: {result.score}/100")
        else:
            gate_text = Text()
            gate_text.append("✗", style="bold red")
            gate_text.append(" Analysis Complete - Gate: ")
            gate_text.append("FAIL", style="bold red")
            gate_text.append(f" - Score: {result.score}/100")

        console.print()
        console.print(self.SEPARATOR, style="dim")
        console.print(gate_text)
        console.print(self.SEPARATOR, style="dim")

        if result.fail_reasons:
            console.print("\nFail reasons:", style="bold")
            for reason in result.fail_reasons:
                console.print(f"  • {reason}", style="red")

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

        # Meta footer
        console.print()
        console.print(self.SEPARATOR, style="dim")
        meta_text = (
            f" Files: {result.meta.get('files_analyzed', 0)} | "
            f"Cache hits: {result.meta.get('cache_hits', 0)} | "
            f"LLM calls: {result.meta.get('llm_calls', 0)} | "
            f"Duration: {result.meta.get('duration_ms', 0)}ms"
        )
        console.print(meta_text, style="dim")
        console.print(self.SEPARATOR, style="dim")

        return buffer.getvalue()
