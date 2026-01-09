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

        # Find the most specific (smallest span) class and function containing the line
        best_class: ast.ClassDef | None = None
        best_class_span = float("inf")
        best_func: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        best_func_span = float("inf")

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and cls._node_contains_line(node, line):
                span = cls._node_span(node)
                if span < best_class_span:
                    best_class = node
                    best_class_span = span

            elif isinstance(  # noqa: UP038
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and cls._node_contains_line(node, line):
                span = cls._node_span(node)
                if span < best_func_span:
                    best_func = node
                    best_func_span = span

        # Build context from best matches
        if best_class is not None:
            # Check if best_func is a method of best_class (direct child)
            for child in ast.iter_child_nodes(best_class):
                if child is best_func:
                    return f"in class {best_class.name}.{best_func.name}()"
            # Function is not a direct method, could be nested - use function if more specific
            if best_func is not None and best_func_span < best_class_span:
                return f"in function {best_func.name}"
            return f"in class {best_class.name}"

        if best_func is not None:
            return f"in function {best_func.name}"

        return None

    @classmethod
    def _node_span(cls, node: ast.AST) -> int:
        """Return the line span of a node."""
        lineno = getattr(node, "lineno", 0)
        end_lineno = getattr(node, "end_lineno", lineno)
        return end_lineno - lineno + 1

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
        except (OSError, UnicodeDecodeError):
            return None
