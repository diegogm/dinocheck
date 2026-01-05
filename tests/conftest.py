"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest

from dinocheck.core.config import DinocheckConfig
from dinocheck.core.types import Issue, IssueLevel, Location
from dinocheck.providers.mock import MockProvider


@pytest.fixture
def mock_provider():
    """Mock LLM provider with deterministic responses."""
    return MockProvider(
        responses={
            "n-plus-one": {
                "issues": [
                    {
                        "rule_id": "django/n-plus-one",
                        "level": "major",
                        "location": {"start_line": 5, "end_line": 7},
                        "title": "N+1 query in loop",
                        "why": "Accessing author inside loop causes N+1 queries",
                        "do": ["Add select_related('author')"],
                        "confidence": 0.95,
                    }
                ]
            },
            "ownership": {
                "issues": [
                    {
                        "rule_id": "django/missing-ownership-filter",
                        "level": "blocker",
                        "location": {"start_line": 10, "end_line": 12},
                        "title": "ViewSet missing ownership filter",
                        "why": "Returns all records without filtering by user",
                        "do": ["Override get_queryset to filter by request.user"],
                        "confidence": 0.98,
                    }
                ]
            },
        }
    )


@pytest.fixture
def sample_config(tmp_path):
    """Sample configuration for testing."""
    return DinocheckConfig(
        packs=["python", "django"],
        model="mock/test-model",
        max_llm_calls=3,
    )


@pytest.fixture
def sample_issues():
    """Sample issues for testing."""
    return [
        Issue(
            rule_id="django/n-plus-one",
            level=IssueLevel.MAJOR,
            location=Location(Path("views.py"), 42, 48),
            title="N+1 query in book_list",
            why="Accessing author inside loop",
            do=["Add select_related('author')"],
            pack="django",
            source="llm",
            confidence=0.95,
        ),
        Issue(
            rule_id="django/missing-ownership-filter",
            level=IssueLevel.BLOCKER,
            location=Location(Path("views.py"), 10, 15),
            title="ViewSet missing ownership filter",
            why="Returns all records without user filter",
            do=["Override get_queryset"],
            pack="django",
            source="llm",
            confidence=0.98,
        ),
        Issue(
            rule_id="python/bare-except",
            level=IssueLevel.MAJOR,
            location=Location(Path("utils.py"), 5, 8),
            title="Bare except block",
            why="Catches all exceptions including KeyboardInterrupt",
            do=["Specify exception type"],
            pack="python",
            source="llm",
            confidence=0.99,
        ),
    ]


@pytest.fixture
def django_test_code():
    """Sample Django code with known issues.

    NOTE: This code intentionally contains anti-patterns (N+1 queries,
    missing ownership filters) to test that dinocheck detects them.
    """
    return """
from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from .models import Book, Order

def book_list(request):
    # N+1 query - should trigger
    books = Book.objects.all()
    return render(request, "books.html", {
        "books": [{"title": b.title, "author": b.author.name} for b in books]
    })

class OrderViewSet(ModelViewSet):
    # Missing ownership filter - should trigger
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
"""


@pytest.fixture
def tmp_python_file(tmp_path, django_test_code):
    """Create a temporary Python file with test code."""
    file_path = tmp_path / "views.py"
    file_path.write_text(django_test_code)
    return file_path


@pytest.fixture
def empty_git_repo(tmp_path):
    """Create an empty git repository."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
    )
    return tmp_path
