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
            "default": {
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

    @pytest.mark.asyncio
    async def test_analyze_empty_paths(self, engine_config):
        """Should handle empty paths list."""
        engine = Engine(engine_config)

        result = await engine.analyze([])

        assert result.issues == []
        assert result.score == 100
        assert result.gate_passed

    @pytest.mark.asyncio
    async def test_analyze_nonexistent_path(self, engine_config, tmp_path):
        """Should handle nonexistent paths gracefully."""
        engine = Engine(engine_config)
        nonexistent = tmp_path / "does_not_exist.py"

        result = await engine.analyze([nonexistent])

        # Should not crash, may have empty issues
        assert isinstance(result.issues, list)

    @pytest.mark.asyncio
    async def test_analyze_simple_python_file(self, engine_config, tmp_path):
        """Should analyze a simple Python file."""
        # Create a simple Python file
        file_path = tmp_path / "simple.py"
        file_path.write_text('''
def hello():
    """Say hello."""
    return "Hello, World!"
''')

        engine = Engine(engine_config)
        result = await engine.analyze([file_path])

        assert isinstance(result.issues, list)
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 100

    @pytest.mark.asyncio
    async def test_analyze_caches_results(self, engine_config, tmp_path):
        """Should cache analysis results."""
        file_path = tmp_path / "cached.py"
        file_path.write_text("def foo(): pass")

        engine = Engine(engine_config)

        # First analysis
        result1 = await engine.analyze([file_path])

        # Second analysis should use cache
        result2 = await engine.analyze([file_path])

        # Results should be consistent
        assert len(result1.issues) == len(result2.issues)

    @pytest.mark.asyncio
    async def test_analyze_django_views(self, engine_config, tmp_path):
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
        result = await engine.analyze([views_path])

        # Should complete without error
        assert isinstance(result.score, int)

    @pytest.mark.asyncio
    async def test_analyze_respects_rule_filter(self, engine_config, tmp_path):
        """Should filter rules when specified."""
        file_path = tmp_path / "test.py"
        file_path.write_text("x = 1")

        engine = Engine(engine_config)

        # Analyze with specific rule filter
        result = await engine.analyze(
            [file_path],
            rule_filter=["django/n-plus-one"],
        )

        # Should complete without error
        assert isinstance(result.issues, list)

    @pytest.mark.asyncio
    async def test_analyze_multiple_files(self, engine_config, tmp_path):
        """Should analyze multiple files."""
        file1 = tmp_path / "file1.py"
        file1.write_text("def foo(): pass")

        file2 = tmp_path / "file2.py"
        file2.write_text("def bar(): pass")

        engine = Engine(engine_config)
        result = await engine.analyze([file1, file2])

        assert isinstance(result.issues, list)
        assert isinstance(result.meta, dict)


class TestEngineWithMockLLM:
    """Tests using mock LLM provider."""

    @pytest.mark.asyncio
    async def test_analyze_with_mock_llm(self, engine_config, mock_provider_with_issues, tmp_path):
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

        result = await engine.analyze([views_path])

        # Should complete analysis
        assert isinstance(result.issues, list)


class TestEngineScoring:
    """Tests for engine scoring integration."""

    @pytest.mark.asyncio
    async def test_score_reflects_issues(self, engine_config, tmp_path, sample_issues):
        """Score should decrease with issues."""
        from dinocheck.core.scoring import calculate_score

        score_no_issues = calculate_score([])
        score_with_issues = calculate_score(sample_issues)

        assert score_no_issues == 100
        assert score_with_issues < score_no_issues

    @pytest.mark.asyncio
    async def test_gate_fails_on_blocker(self, sample_issues):
        """Gate should fail on blocker issues."""
        from dinocheck.core.scoring import check_gate
        from dinocheck.core.types import Issue, IssueLevel, Location

        # Create a blocker issue
        blocker = Issue(
            rule_id="python/sql-injection",
            level=IssueLevel.BLOCKER,
            location=Location(Path("app.py"), 1, 5),
            title="SQL Injection",
            why="User input in query",
            do=["Use parameterized query"],
            pack="python",
        )

        passed, reasons = check_gate([blocker])
        assert not passed
        assert len(reasons) > 0
