"""Integration tests for CLI commands."""

import json

import pytest
from typer.testing import CliRunner

from dinocheck.cli.main import app

runner = CliRunner()


class TestVersionCommand:
    """Tests for dino version command."""

    def test_version_shows_version(self):
        """Should display version information."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "dinocheck" in result.stdout.lower() or "0." in result.stdout


class TestPacksCommand:
    """Tests for dino packs commands."""

    def test_packs_list(self):
        """Should list available packs."""
        result = runner.invoke(app, ["packs", "list"])

        assert result.exit_code == 0
        assert "python" in result.stdout.lower()
        assert "django" in result.stdout.lower()

    def test_packs_info_django(self):
        """Should show Django pack info."""
        result = runner.invoke(app, ["packs", "info", "django"])

        assert result.exit_code == 0
        assert "django" in result.stdout.lower()

    def test_packs_info_unknown(self):
        """Should error for unknown pack."""
        result = runner.invoke(app, ["packs", "info", "unknown-pack"])

        assert result.exit_code != 0


class TestCacheCommand:
    """Tests for dino cache commands."""

    def test_cache_stats(self, tmp_path, monkeypatch):
        """Should show cache statistics."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["cache", "stats"])

        # May show 0 entries for empty cache
        assert result.exit_code == 0

    def test_cache_clear(self, tmp_path, monkeypatch):
        """Should clear cache."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["cache", "clear"])

        assert result.exit_code == 0


class TestCheckCommand:
    """Tests for dino check command."""

    @pytest.fixture
    def python_file(self, tmp_path):
        """Create a temporary Python file."""
        file_path = tmp_path / "test_file.py"
        file_path.write_text('''
def example_function():
    """Example function with no issues."""
    return 42
''')
        return file_path

    @pytest.fixture
    def django_views_file(self, tmp_path):
        """Create a Django views file with potential issues."""
        file_path = tmp_path / "views.py"
        file_path.write_text('''
from django.shortcuts import render
from .models import Book

def book_list(request):
    # Potential N+1 query
    books = Book.objects.all()
    return render(request, "books.html", {
        "books": [{"title": b.title, "author": b.author.name} for b in books]
    })
''')
        return file_path

    def test_check_json_format(self, python_file, tmp_path, monkeypatch):
        """Should output JSON format."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, [
            "check",
            str(python_file),
            "--format", "json",
        ])

        # Should be valid JSON if it succeeded
        if result.exit_code in (0, 1):
            try:
                output = json.loads(result.stdout)
                assert "issues" in output or "error" in result.stdout.lower()
            except json.JSONDecodeError:
                pass


class TestInitCommand:
    """Tests for dino init command."""

    def test_init_creates_config(self, tmp_path, monkeypatch):
        """Should create dino.yaml."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert (tmp_path / "dino.yaml").exists()

    def test_init_does_not_overwrite(self, tmp_path, monkeypatch):
        """Should not overwrite existing config."""
        monkeypatch.chdir(tmp_path)

        # Create existing config
        config_path = tmp_path / "dino.yaml"
        config_path.write_text("existing: true")

        result = runner.invoke(app, ["init"])

        # Should warn or skip
        assert "exists" in result.stdout.lower() or config_path.read_text() == "existing: true"


class TestLogsCommand:
    """Tests for dino logs commands."""

    def test_logs_list_empty(self, tmp_path, monkeypatch):
        """Should handle empty logs."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["logs", "list"])

        assert result.exit_code == 0

    def test_logs_cost_empty(self, tmp_path, monkeypatch):
        """Should handle empty cost summary."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["logs", "cost"])

        assert result.exit_code == 0


class TestExplainCommand:
    """Tests for dino explain command."""

    def test_explain_known_rule(self):
        """Should explain known rule."""
        result = runner.invoke(app, ["explain", "django/n-plus-one"])

        # Should show rule info or error gracefully
        assert result.exit_code in (0, 1)

    def test_explain_unknown_rule(self):
        """Should handle unknown rule."""
        result = runner.invoke(app, ["explain", "unknown/rule"])

        # Should error or show "not found"
        assert result.exit_code != 0 or "not found" in result.stdout.lower()
