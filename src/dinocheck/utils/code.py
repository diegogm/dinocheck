"""Code analysis utilities."""

import ast
from pathlib import Path


class CodeExtractor:
    """Extracts code snippets and context from source files."""

    CONTEXT_LINES = 2  # Lines before/after the issue to show

    @classmethod
    def extract_snippet(
        cls,
        content: str,
        start_line: int,
        end_line: int | None = None,
    ) -> str:
        """Extract a code snippet around the specified lines.

        Args:
            content: Full file content
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based), defaults to start_line

        Returns:
            Formatted code snippet with line numbers
        """
        lines = content.splitlines()
        end_line = end_line or start_line

        # Calculate range with context
        snippet_start = max(0, start_line - cls.CONTEXT_LINES - 1)
        snippet_end = min(len(lines), end_line + cls.CONTEXT_LINES)

        # Build snippet with line numbers
        result = []
        for i in range(snippet_start, snippet_end):
            line_num = i + 1
            marker = ">" if start_line <= line_num <= end_line else " "
            result.append(f"{marker} {line_num:4d} | {lines[i]}")

        return "\n".join(result)

    @classmethod
    def extract_context(cls, content: str, line: int) -> str | None:
        """Extract the function/class/method name containing the line.

        Args:
            content: Full file content
            line: Line number (1-based)

        Returns:
            Context string like "in function foo" or "in class Bar.method"
        """
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return None

        context_parts: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and cls._node_contains_line(node, line):
                context_parts = [f"class {node.name}"]
                # Check for method inside class
                for child in ast.iter_child_nodes(node):
                    if isinstance(  # noqa: UP038
                        child, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ) and cls._node_contains_line(child, line):
                        context_parts.append(child.name)
                        break

            elif (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))  # noqa: UP038
                and cls._node_contains_line(node, line)
                and not context_parts
            ):
                context_parts = [f"function {node.name}"]

        if not context_parts:
            return None

        if len(context_parts) == 1:
            return f"in {context_parts[0]}"
        return f"in {context_parts[0]}.{context_parts[1]}()"

    @classmethod
    def _node_contains_line(cls, node: ast.AST, line: int) -> bool:
        """Check if an AST node contains the specified line."""
        lineno = getattr(node, "lineno", None)
        end_lineno = getattr(node, "end_lineno", None)
        if lineno is None:
            return False
        start: int = lineno
        end: int = end_lineno if end_lineno is not None else start
        return start <= line <= end

    @classmethod
    def extract_snippet_from_file(
        cls,
        path: Path,
        start_line: int,
        end_line: int | None = None,
    ) -> str | None:
        """Extract snippet from a file path."""
        try:
            content = path.read_text()
            return cls.extract_snippet(content, start_line, end_line)
        except (OSError, UnicodeDecodeError):
            return None

    @classmethod
    def extract_context_from_file(cls, path: Path, line: int) -> str | None:
        """Extract context from a file path."""
        try:
            content = path.read_text()
            return cls.extract_context(content, line)
        except (OSError, UnicodeDecodeError, SyntaxError):
            return None
