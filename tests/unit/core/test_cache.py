"""Tests for SQLite cache."""

import sqlite3
from pathlib import Path

import pytest

from dinocheck.core.cache import SQLiteCache
from dinocheck.core.migrations import MIGRATIONS, Migrator
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


# Legacy schema with prompt_text and response_text columns (version 0)
_LEGACY_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    rules_hash TEXT NOT NULL,
    issues_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_hash, rules_hash)
);
CREATE TABLE IF NOT EXISTS llm_logs (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model TEXT NOT NULL,
    pack TEXT NOT NULL,
    files_json TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    duration_ms INTEGER NOT NULL,
    issues_found INTEGER NOT NULL,
    cached INTEGER DEFAULT 0,
    prompt_text TEXT,
    response_text TEXT
);
"""


class TestMigrations:
    """Tests for schema migration system."""

    def test_new_database_has_current_version(self, tmp_path):
        """A freshly created database should have CURRENT_VERSION."""
        db_path = tmp_path / "new.db"
        SQLiteCache(db_path, ttl_hours=1)
        conn = sqlite3.connect(db_path)
        try:
            version = Migrator.get_version(conn)
            assert version == SQLiteCache.CURRENT_VERSION
        finally:
            conn.close()

    def test_migrate_from_legacy_database(self, tmp_path):
        """Opening a legacy DB (version 0) should drop prompt/response columns and preserve data."""
        db_path = tmp_path / "legacy.db"

        # Create a legacy database at version 0 with old columns
        conn = sqlite3.connect(db_path)
        conn.executescript(_LEGACY_SCHEMA)
        conn.execute(
            """INSERT INTO llm_logs
               (id, model, pack, files_json, prompt_tokens, completion_tokens,
                total_tokens, cost_usd, duration_ms, issues_found, cached,
                prompt_text, response_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "log-1",
                "gpt-4o-mini",
                "django",
                '["views.py"]',
                100,
                50,
                150,
                0.01,
                1500,
                3,
                0,
                "prompt",
                "response",
            ),
        )
        conn.commit()
        conn.close()

        # Open with new code — migrations should run
        cache = SQLiteCache(db_path, ttl_hours=1)

        # Verify data preserved
        logs = cache.get_llm_logs(limit=10)
        assert len(logs) == 1
        assert logs[0].model == "gpt-4o-mini"
        assert logs[0].total_tokens == 150

        # Verify columns are gone
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(llm_logs)")
        col_names = {row[1] for row in cursor.fetchall()}
        assert "prompt_text" not in col_names
        assert "response_text" not in col_names

        # Verify version updated
        assert Migrator.get_version(conn) == SQLiteCache.CURRENT_VERSION
        conn.close()

    def test_migration_is_idempotent(self, tmp_path):
        """Running migrations twice should not raise errors."""
        db_path = tmp_path / "idempotent.db"

        # Create legacy database
        conn = sqlite3.connect(db_path)
        conn.executescript(_LEGACY_SCHEMA)
        conn.commit()
        conn.close()

        # Open twice — second time migrations are already applied
        SQLiteCache(db_path, ttl_hours=1)
        SQLiteCache(db_path, ttl_hours=1)

        # Verify version is correct
        conn = sqlite3.connect(db_path)
        assert Migrator.get_version(conn) == SQLiteCache.CURRENT_VERSION
        conn.close()

    def test_target_exceeds_available_migrations(self, tmp_path):
        """Should raise ValueError when target version exceeds available migrations."""
        db_path = tmp_path / "exceed.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(_LEGACY_SCHEMA)
        conn.commit()

        migrator = Migrator(MIGRATIONS)
        with pytest.raises(ValueError, match="exceeds available migrations"):
            migrator.apply_pending(conn, len(MIGRATIONS) + 1)
        conn.close()

    def test_downgrade_raises_error(self, tmp_path):
        """Should raise ValueError when attempting to downgrade."""
        db_path = tmp_path / "downgrade.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(_LEGACY_SCHEMA)
        Migrator.set_version(conn, 1)
        conn.commit()

        migrator = Migrator(MIGRATIONS)
        with pytest.raises(ValueError, match="Downgrade .* not supported"):
            migrator.apply_pending(conn, 0)
        conn.close()
