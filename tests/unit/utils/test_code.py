"""Tests for code extraction utilities."""

import tempfile
from pathlib import Path

from dinocheck.utils.code import CodeExtractor


class TestExtractSnippet:
    """Tests for CodeExtractor.extract_snippet."""

    def test_extract_single_line(self) -> None:
        """Should extract a single line with context."""
        content = """line 1
line 2
line 3
line 4
line 5"""
        result = CodeExtractor.extract_snippet(content, 3)

        assert "> " in result  # Marker for highlighted line
        assert "line 3" in result
        assert "line 1" in result  # Context before
        assert "line 5" in result  # Context after

    def test_extract_line_range(self) -> None:
        """Should extract multiple lines."""
        content = """def foo():
    x = 1
    y = 2
    return x + y
"""
        result = CodeExtractor.extract_snippet(content, 2, 3)

        # Lines 2 and 3 should be marked
        lines = result.splitlines()
        marked_lines = [line for line in lines if line.startswith(">")]
        assert len(marked_lines) == 2

    def test_extract_at_file_start(self) -> None:
        """Should handle extraction at the start of file."""
        content = """first line
second line
third line"""
        result = CodeExtractor.extract_snippet(content, 1)

        assert "first line" in result
        # Should not crash on context before line 1

    def test_extract_at_file_end(self) -> None:
        """Should handle extraction at the end of file."""
        content = """line 1
line 2
last line"""
        result = CodeExtractor.extract_snippet(content, 3)

        assert "last line" in result
        # Should not crash on context after last line

    def test_line_numbers_in_snippet(self) -> None:
        """Should include line numbers in output."""
        content = "line\n" * 10
        result = CodeExtractor.extract_snippet(content, 5)

        assert "5 |" in result


class TestExtractContext:
    """Tests for CodeExtractor.extract_context."""

    def test_context_in_function(self) -> None:
        """Should return function context."""
        content = """def my_function():
    x = 1
    return x
"""
        result = CodeExtractor.extract_context(content, 2)
        assert result == "in function my_function"

    def test_context_in_async_function(self) -> None:
        """Should handle async functions."""
        content = """async def async_handler():
    await something()
    return result
"""
        result = CodeExtractor.extract_context(content, 2)
        assert result == "in function async_handler"

    def test_context_in_class(self) -> None:
        """Should return class context."""
        content = """class MyClass:
    x = 1
    y = 2
"""
        result = CodeExtractor.extract_context(content, 2)
        assert result == "in class MyClass"

    def test_context_in_method(self) -> None:
        """Should return class.method context."""
        content = """class MyClass:
    def my_method(self):
        return 42
"""
        result = CodeExtractor.extract_context(content, 3)
        assert result == "in class MyClass.my_method()"

    def test_context_in_async_method(self) -> None:
        """Should handle async methods."""
        content = """class Handler:
    async def handle(self):
        await self.process()
"""
        result = CodeExtractor.extract_context(content, 3)
        assert result == "in class Handler.handle()"

    def test_context_outside_function(self) -> None:
        """Should return None for module-level code."""
        content = """import os
x = 1
print(x)
"""
        result = CodeExtractor.extract_context(content, 2)
        assert result is None

    def test_context_syntax_error(self) -> None:
        """Should handle syntax errors gracefully."""
        content = """def broken(
    missing closing paren
"""
        result = CodeExtractor.extract_context(content, 2)
        assert result is None

    def test_context_in_nested_function(self) -> None:
        """Should return innermost nested function context."""
        content = """def outer():
    def inner():
        x = 1
        return x
    return inner
"""
        # Line 3 is inside inner(), not outer()
        result = CodeExtractor.extract_context(content, 3)
        assert result == "in function inner"

    def test_context_in_closure(self) -> None:
        """Should return closure function context."""
        content = """def make_adder(n):
    def adder(x):
        return x + n
    return adder
"""
        # Line 3 is inside adder(), the closure
        result = CodeExtractor.extract_context(content, 3)
        assert result == "in function adder"


class TestNodeContainsLine:
    """Tests for CodeExtractor._node_contains_line."""

    def test_line_in_range(self) -> None:
        """Should return True when line is in node range."""
        import ast

        content = """def foo():
    x = 1
    return x
"""
        tree = ast.parse(content)
        func_node = tree.body[0]

        assert CodeExtractor._node_contains_line(func_node, 1)
        assert CodeExtractor._node_contains_line(func_node, 2)
        assert CodeExtractor._node_contains_line(func_node, 3)

    def test_line_outside_range(self) -> None:
        """Should return False when line is outside node range."""
        import ast

        content = """x = 1

def foo():
    return 42
"""
        tree = ast.parse(content)
        func_node = tree.body[1]

        assert not CodeExtractor._node_contains_line(func_node, 1)

    def test_node_without_lineno(self) -> None:
        """Should return False for nodes without lineno."""
        import ast

        node = ast.Module(body=[], type_ignores=[])
        assert not CodeExtractor._node_contains_line(node, 1)


class TestExtractFromFile:
    """Tests for file-based extraction methods."""

    def test_extract_snippet_from_file(self) -> None:
        """Should read and extract from a file."""
        content = """def hello():
    print("world")
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
            path = Path(f.name)

        try:
            result = CodeExtractor.extract_snippet_from_file(path, 2)
            assert result is not None
            assert "print" in result
        finally:
            path.unlink()

    def test_extract_snippet_from_nonexistent_file(self) -> None:
        """Should return None for nonexistent file."""
        path = Path("/nonexistent/file.py")
        result = CodeExtractor.extract_snippet_from_file(path, 1)
        assert result is None

    def test_extract_context_from_file(self) -> None:
        """Should read and extract context from a file."""
        content = """def my_func():
    return 42
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            f.flush()
            path = Path(f.name)

        try:
            result = CodeExtractor.extract_context_from_file(path, 2)
            assert result == "in function my_func"
        finally:
            path.unlink()

    def test_extract_context_from_nonexistent_file(self) -> None:
        """Should return None for nonexistent file."""
        path = Path("/nonexistent/file.py")
        result = CodeExtractor.extract_context_from_file(path, 1)
        assert result is None
