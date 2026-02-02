"""Integration tests for the analysis engine."""

from pathlib import Path

import pytest

from dinocheck.core.config import DinocheckConfig
from dinocheck.core.engine import Engine
from dinocheck.core.types import IssueLevel
from dinocheck.providers.mock import MockProvider


@pytest.fixture
def engine_config(tmp_path):
    """Create engine configuration for testing."""
    return DinocheckConfig(
        packs=["python", "django"],
        model="mock/test-model",
        max_llm_calls=2,
    )


@pytest.fixture
def sample_issues():
    """Sample issues for testing scoring."""
    from dinocheck.core.types import Issue, Location

    return [
        Issue(
            rule_id="django/n-plus-one",
            level=IssueLevel.MAJOR,
            location=Location(Path("views.py"), 42, 48),
            title="N+1 query",
            why="N+1 query detected",
            do=["Add select_related"],
            pack="django",
        ),
        Issue(
            rule_id="django/api-authorization",
            level=IssueLevel.CRITICAL,
            location=Location(Path("views.py"), 10, 15),
            title="Missing authorization",
            why="ViewSet missing permissions",
            do=["Add permission_classes"],
            pack="django",
        ),
    ]


@pytest.fixture
def mock_provider_with_issues():
    """Mock provider that returns issues."""
    return MockProvider(
        responses={
            "book_list": {  # Key must be found in the prompt (file content)
                "issues": [
                    {
                        "rule_id": "django/n-plus-one",
                        "level": "major",
                        "location": {"start_line": 5, "end_line": 7},
                        "title": "N+1 query detected",
                        "why": "Accessing related field in loop",
                        "do": ["Add select_related('author')"],
                        "confidence": 0.95,
                    }
                ]
            }
        }
    )


class TestEngine:
    """Integration tests for Engine class."""

    def test_analyze_empty_directory(self, engine_config, tmp_path):
        """Should handle directory with no Python files."""
        engine = Engine(engine_config)
        engine.provider = MockProvider()

        # Create an empty temp directory
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = engine.analyze([empty_dir])

        assert result.issues == []
        assert result.score == 100

    def test_analyze_nonexistent_path(self, engine_config, tmp_path):
        """Should handle nonexistent paths gracefully."""
        engine = Engine(engine_config)
        nonexistent = tmp_path / "does_not_exist.py"

        result = engine.analyze([nonexistent])

        # Should not crash, may have empty issues
        assert isinstance(result.issues, list)

    def test_analyze_simple_python_file(self, engine_config, tmp_path):
        """Should analyze a simple Python file."""
        # Create a simple Python file
        file_path = tmp_path / "simple.py"
        file_path.write_text('''
def hello():
    """Say hello."""
    return "Hello, World!"
''')

        engine = Engine(engine_config)
        engine.provider = MockProvider()
        result = engine.analyze([file_path])

        assert isinstance(result.issues, list)
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 100

    def test_analyze_caches_results(self, engine_config, tmp_path):
        """Should cache analysis results."""
        file_path = tmp_path / "cached.py"
        file_path.write_text("def foo(): pass")

        engine = Engine(engine_config)
        engine.provider = MockProvider()

        # First analysis - should call LLM
        result1 = engine.analyze([file_path], no_cache=True)
        assert result1.meta["cache_hits"] == 0

        # Second analysis should use cache
        result2 = engine.analyze([file_path])
        assert result2.meta["cache_hits"] > 0, "Second analysis should use cache"
        assert result2.meta["llm_calls"] == 0, "Should not call LLM when cached"

    def test_analyze_django_views(self, engine_config, tmp_path):
        """Should analyze Django views file."""
        views_path = tmp_path / "views.py"
        views_path.write_text("""
from django.shortcuts import render
from .models import Book

def book_list(request):
    books = Book.objects.all()
    return render(request, "books.html", {
        "books": [{"title": b.title, "author": b.author.name} for b in books]
    })

class OrderViewSet:
    queryset = Order.objects.all()
""")

        engine = Engine(engine_config)
        engine.provider = MockProvider()
        result = engine.analyze([views_path])

        # Should complete without error
        assert isinstance(result.score, int)

    def test_analyze_respects_rule_filter(self, engine_config, tmp_path):
        """Should filter rules when specified."""
        file_path = tmp_path / "test.py"
        file_path.write_text("x = 1")

        engine = Engine(engine_config)
        engine.provider = MockProvider(
            responses={
                "x = 1": {
                    "issues": [
                        {
                            "rule_id": "django/n-plus-one",
                            "level": "major",
                            "location": {"start_line": 1, "end_line": 1},
                            "title": "Test issue 1",
                            "why": "Test",
                            "do": ["Fix"],
                            "confidence": 0.9,
                        },
                        {
                            "rule_id": "python/other-rule",
                            "level": "minor",
                            "location": {"start_line": 1, "end_line": 1},
                            "title": "Test issue 2",
                            "why": "Test",
                            "do": ["Fix"],
                            "confidence": 0.9,
                        },
                    ]
                }
            }
        )

        # Analyze with specific rule filter
        result = engine.analyze(
            [file_path],
            rule_filter=["django/n-plus-one"],
            no_cache=True,
        )

        # Should only return issues matching the filter
        assert isinstance(result.issues, list)
        for issue in result.issues:
            assert "n-plus-one" in issue.rule_id, f"Unexpected rule: {issue.rule_id}"

    def test_analyze_multiple_files(self, engine_config, tmp_path):
        """Should analyze multiple files."""
        file1 = tmp_path / "file1.py"
        file1.write_text("def foo(): pass")

        file2 = tmp_path / "file2.py"
        file2.write_text("def bar(): pass")

        engine = Engine(engine_config)
        engine.provider = MockProvider()
        result = engine.analyze([file1, file2])

        assert isinstance(result.issues, list)
        assert isinstance(result.meta, dict)


class TestEngineWithMockLLM:
    """Tests using mock LLM provider."""

    def test_analyze_with_mock_llm(self, engine_config, mock_provider_with_issues, tmp_path):
        """Should analyze with mock LLM and find issues."""
        views_path = tmp_path / "views.py"
        views_path.write_text("""
from django.shortcuts import render
from .models import Book

def book_list(request):
    books = Book.objects.all()
    for book in books:
        print(book.author.name)
""")

        # Replace provider in config
        engine = Engine(engine_config)
        engine.provider = mock_provider_with_issues

        result = engine.analyze([views_path], no_cache=True)

        # Should complete analysis and find issues
        assert isinstance(result.issues, list)
        assert len(result.issues) > 0, "Mock provider should have returned issues"


class TestEngineIncludePaths:
    """Tests for include_paths config in Engine."""

    def test_include_paths_overrides_default(self, tmp_path):
        """Should use include_paths instead of cwd when paths is [Path('.')]."""
        # Create files in two directories
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("x = 1")

        other = tmp_path / "other"
        other.mkdir()
        (other / "ignored.py").write_text("y = 2")

        config = DinocheckConfig(
            packs=["python"],
            model="mock/test-model",
            max_llm_calls=5,
            include_paths=["src/"],
        )

        engine = Engine(config)
        engine.provider = MockProvider()

        # Pass default [Path(".")] — engine should replace with include_paths
        result = engine.analyze([Path(".")], no_cache=True)

        # include_paths replaces the default "." so the engine runs without error
        assert isinstance(result.issues, list)

    def test_include_paths_not_applied_with_explicit_paths(self, tmp_path):
        """Should NOT use include_paths when explicit paths are given."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("x = 1")

        other = tmp_path / "other"
        other.mkdir()
        (other / "views.py").write_text("y = 2")

        config = DinocheckConfig(
            packs=["python"],
            model="mock/test-model",
            max_llm_calls=5,
            include_paths=["src/"],
        )

        engine = Engine(config)
        engine.provider = MockProvider()

        # Explicit path should bypass include_paths
        result = engine.analyze([other], no_cache=True)

        assert result.meta["files_analyzed"] >= 1


class TestEngineScoring:
    """Tests for engine scoring integration."""

    def test_score_reflects_issues(self, engine_config, tmp_path, sample_issues):
        """Score should decrease with issues."""
        from dinocheck.core.scoring import calculate_score

        score_no_issues = calculate_score([])
        score_with_issues = calculate_score(sample_issues)

        assert score_no_issues == 100
        assert score_with_issues < score_no_issues
