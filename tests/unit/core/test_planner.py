"""Tests for the analysis planner."""

import pytest

from dinocheck.core.cache import SQLiteCache
from dinocheck.core.config import DinocheckConfig
from dinocheck.core.planner import AnalysisPlanner


@pytest.fixture
def cache(tmp_path):
    """Create a temporary cache."""
    return SQLiteCache(tmp_path / "cache.db", ttl_hours=1)


@pytest.fixture
def config():
    """Config with python and django packs."""
    return DinocheckConfig(packs=["python", "django"])


@pytest.fixture
def django_views(tmp_path):
    """Django views file that triggers ORM rules."""
    views = tmp_path / "views.py"
    views.write_text(
        """
from .models import Book

def book_list(request):
    for b in Book.objects.all():
        print(b.author.name)
"""
    )
    return views


class TestAnalysisPlanner:
    """Tests for AnalysisPlanner."""

    def test_plan_creates_tasks_with_rules(self, config, cache, django_views):
        """Files matching rule triggers become tasks with those rules."""
        planner = AnalysisPlanner(config, cache, analyzer="agent")
        plan = planner.plan([django_views])

        assert plan.files_total == 1
        assert len(plan.tasks) == 1
        task = plan.tasks[0]
        assert task.file_ctx.path == django_views
        assert len(task.rules) > 0
        assert task.file_hash
        assert task.rules_hash

    def test_plan_empty_directory(self, config, cache, tmp_path):
        """Empty directory produces an empty plan."""
        empty = tmp_path / "empty"
        empty.mkdir()

        planner = AnalysisPlanner(config, cache, analyzer="agent")
        plan = planner.plan([empty])

        assert plan.files_total == 0
        assert plan.tasks == []
        assert plan.cached_issues == []

    def test_plan_resolves_cache_hits(self, config, cache, django_views):
        """A cached file is not planned as a task again."""
        planner = AnalysisPlanner(config, cache, analyzer="agent")
        plan = planner.plan([django_views])
        task = plan.tasks[0]

        cache.put(task.file_hash, task.rules_hash, "agent", [])

        replan = planner.plan([django_views])
        assert replan.tasks == []
        assert replan.cache_hits == 1

    def test_plan_cache_is_analyzer_specific(self, config, cache, django_views):
        """A cache entry from another analyzer does not satisfy the plan."""
        planner = AnalysisPlanner(config, cache, analyzer="agent")
        plan = planner.plan([django_views])
        task = plan.tasks[0]

        cache.put(task.file_hash, task.rules_hash, "openai/gpt-4o", [])

        replan = planner.plan([django_views])
        assert len(replan.tasks) == 1
        assert replan.cache_hits == 0

    def test_plan_no_cache_skips_lookup(self, config, cache, django_views):
        """no_cache=True re-plans files even when cached."""
        planner = AnalysisPlanner(config, cache, analyzer="agent")
        plan = planner.plan([django_views])
        task = plan.tasks[0]
        cache.put(task.file_hash, task.rules_hash, "agent", [])

        replan = planner.plan([django_views], no_cache=True)
        assert len(replan.tasks) == 1

    def test_plan_applies_rule_filter(self, config, cache, django_views):
        """rule_filter restricts the rules attached to each task."""
        planner = AnalysisPlanner(config, cache, analyzer="agent")
        plan = planner.plan([django_views], rule_filter=["n-plus-one"])

        for task in plan.tasks:
            assert all("n-plus-one" in rule.id for rule in task.rules)

    def test_plan_uses_include_paths_for_default_path(self, config, cache, tmp_path, monkeypatch):
        """Default path '.' is replaced by config include_paths."""
        from pathlib import Path

        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "views.py").write_text("for b in Book.objects.all():\n    pass\n")
        other = tmp_path / "other"
        other.mkdir()
        (other / "views.py").write_text("for b in Book.objects.all():\n    pass\n")

        config.include_paths = ["src/"]
        planner = AnalysisPlanner(config, cache, analyzer="agent")
        plan = planner.plan([Path(".")])

        planned_paths = [str(task.file_ctx.path) for task in plan.tasks]
        assert all("other" not in p for p in planned_paths)
