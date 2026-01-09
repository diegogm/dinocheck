"""Tests for SQLite cache."""

from pathlib import Path

import pytest

from dinocheck.core.cache import SQLiteCache
from dinocheck.core.types import Issue, IssueLevel, Location
from dinocheck.utils.hashing import ContentHasher


@pytest.fixture
def cache(tmp_path):
    """Create a temporary cache."""
    db_path = tmp_path / "cache.db"
    return SQLiteCache(db_path, ttl_hours=1)


@pytest.fixture
def sample_issue():
    """Create a sample issue."""
    return Issue(
        rule_id="test/rule",
        level=IssueLevel.MAJOR,
        location=Location(Path("test.py"), 10, 15),
        title="Test issue",
        why="Test reason",
        do=["Fix it"],
        pack="test",
        source="llm",
        confidence=0.9,
    )


class TestSQLiteCache:
    """Tests for SQLiteCache class."""

    def test_put_and_get(self, cache, sample_issue):
        """Should store and retrieve issues."""
        cache.put("hash1", "rules1", [sample_issue])
        result = cache.get("hash1", "rules1")

        assert result is not None
        assert len(result) == 1
        assert result[0].rule_id == "test/rule"
        assert result[0].title == "Test issue"

    def test_cache_miss(self, cache, sample_issue):
        """Should return None for missing key."""
        cache.put("hash1", "rules1", [sample_issue])
        result = cache.get("hash2", "rules1")

        assert result is None

    def test_cache_miss_different_rules(self, cache, sample_issue):
        """Should return None for different rules hash."""
        cache.put("hash1", "rules1", [sample_issue])
        result = cache.get("hash1", "rules2")

        assert result is None

    def test_cache_update(self, cache, sample_issue):
        """Should update existing cache entry."""
        cache.put("hash1", "rules1", [sample_issue])

        new_issue = Issue(
            rule_id="test/other",
            level=IssueLevel.MINOR,
            location=Location(Path("test.py"), 5),
            title="Other issue",
            why="Other reason",
            do=["Other fix"],
            pack="test",
            source="llm",
        )
        cache.put("hash1", "rules1", [new_issue])

        result = cache.get("hash1", "rules1")
        assert len(result) == 1
        assert result[0].rule_id == "test/other"

    def test_clear_all(self, cache, sample_issue):
        """Should clear all cache entries."""
        cache.put("hash1", "rules1", [sample_issue])
        cache.put("hash2", "rules1", [sample_issue])

        deleted = cache.clear()

        assert deleted == 2
        assert cache.get("hash1", "rules1") is None
        assert cache.get("hash2", "rules1") is None

    def test_stats(self, cache, sample_issue):
        """Should return cache statistics."""
        cache.put("hash1", "rules1", [sample_issue])
        cache.put("hash2", "rules1", [sample_issue])

        stats = cache.stats()

        assert stats.entries == 2
        assert stats.size_bytes > 0


class TestLLMLogging:
    """Tests for LLM call logging."""

    def test_log_llm_call(self, cache):
        """Should log LLM call and return cost."""
        cost_usd = cache.log_llm_call(
            model="gpt-4o-mini",
            pack="django",
            files=["views.py"],
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=1500,
            issues_found=3,
        )

        # log_llm_call returns cost_usd (float)
        assert isinstance(cost_usd, float)
        assert cost_usd >= 0.0

    def test_get_llm_logs(self, cache):
        """Should retrieve LLM logs."""
        cache.log_llm_call(
            model="gpt-4o-mini",
            pack="django",
            files=["views.py"],
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=1500,
            issues_found=3,
        )

        logs = cache.get_llm_logs(limit=10)

        assert len(logs) == 1
        assert logs[0].model == "gpt-4o-mini"
        assert logs[0].pack == "django"
        assert logs[0].total_tokens == 150

    def test_get_cost_summary(self, cache):
        """Should calculate cost summary."""
        cache.log_llm_call(
            model="gpt-4o-mini",
            pack="django",
            files=["views.py"],
            prompt_tokens=1000,
            completion_tokens=500,
            duration_ms=1500,
            issues_found=3,
            cost_usd=0.01,
        )
        cache.log_llm_call(
            model="gpt-4o-mini",
            pack="django",
            files=["models.py"],
            prompt_tokens=800,
            completion_tokens=400,
            duration_ms=1200,
            issues_found=2,
            cost_usd=0.008,
        )

        summary = cache.get_cost_summary(days=30)

        assert summary.total_calls == 2
        assert summary.total_tokens == 2700
        assert summary.total_cost == pytest.approx(0.018, rel=0.01)
        assert summary.total_issues == 5


class TestContentHasher:
    """Tests for ContentHasher."""

    def test_hash_content_consistency(self):
        """Same content should produce same hash."""
        content = "def foo():\n    pass"
        hash1 = ContentHasher.hash_content(content)
        hash2 = ContentHasher.hash_content(content)
        assert hash1 == hash2

    def test_hash_content_trailing_whitespace_normalized(self):
        """Trailing whitespace should be normalized."""
        hash1 = ContentHasher.hash_content("def foo():    \n    pass")
        hash2 = ContentHasher.hash_content("def foo():\n    pass")
        # Trailing whitespace stripped - same hash
        assert hash1 == hash2

    def test_hash_content_preserves_indentation(self):
        """Indentation differences should produce different hash."""
        hash1 = ContentHasher.hash_content("def foo():\n    pass")
        hash2 = ContentHasher.hash_content("def foo():\n        pass")
        # Different indentation = different code = different hash
        assert hash1 != hash2

    def test_hash_content_different_content(self):
        """Different content should produce different hash."""
        hash1 = ContentHasher.hash_content("def foo(): pass")
        hash2 = ContentHasher.hash_content("def bar(): pass")
        assert hash1 != hash2

    def test_hash_rules_consistency(self):
        """Same rules should produce same hash."""
        rules = ["django/n-plus-one", "django/ownership"]
        hash1 = ContentHasher.hash_rules(rules)
        hash2 = ContentHasher.hash_rules(rules)
        assert hash1 == hash2

    def test_hash_rules_order_independent(self):
        """Different order should produce same hash."""
        hash1 = ContentHasher.hash_rules(["django/a", "django/b"])
        hash2 = ContentHasher.hash_rules(["django/b", "django/a"])
        assert hash1 == hash2

    def test_create_cache_key(self):
        """Should create CacheKey with both hashes."""
        key = ContentHasher.create_cache_key("def foo(): pass", ["rule/a", "rule/b"])
        assert key.file_hash
        assert key.rules_hash
        assert len(key.file_hash) == 32
        assert len(key.rules_hash) == 32
