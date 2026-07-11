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
        cache.put("hash1", "rules1", "model-a", [sample_issue])
        result = cache.get("hash1", "rules1", "model-a")

        assert result is not None
        assert len(result) == 1
        assert result[0].rule_id == "test/rule"
        assert result[0].title == "Test issue"

    def test_cache_miss(self, cache, sample_issue):
        """Should return None for missing key."""
        cache.put("hash1", "rules1", "model-a", [sample_issue])
        result = cache.get("hash2", "rules1", "model-a")

        assert result is None

    def test_cache_miss_different_rules(self, cache, sample_issue):
        """Should return None for different rules hash."""
        cache.put("hash1", "rules1", "model-a", [sample_issue])
        result = cache.get("hash1", "rules2", "model-a")

        assert result is None

    def test_cache_miss_different_analyzer(self, cache, sample_issue):
        """Results from different analyzers must not collide."""
        cache.put("hash1", "rules1", "model-a", [sample_issue])

        assert cache.get("hash1", "rules1", "agent") is None
        assert cache.get("hash1", "rules1", "model-b") is None
        assert cache.get("hash1", "rules1", "model-a") is not None

    def test_analyzers_store_independent_results(self, cache, sample_issue):
        """Same file+rules can hold one entry per analyzer."""
        other_issue = Issue(
            rule_id="test/agent-rule",
            level=IssueLevel.MINOR,
            location=Location(Path("test.py"), 3),
            title="Agent issue",
            why="Agent reason",
            do=["Fix"],
            pack="test",
            source="agent",
        )
        cache.put("hash1", "rules1", "model-a", [sample_issue])
        cache.put("hash1", "rules1", "agent", [other_issue])

        model_result = cache.get("hash1", "rules1", "model-a")
        agent_result = cache.get("hash1", "rules1", "agent")
        assert model_result[0].rule_id == "test/rule"
        assert agent_result[0].rule_id == "test/agent-rule"

    def test_cache_update(self, cache, sample_issue):
        """Should update existing cache entry."""
        cache.put("hash1", "rules1", "model-a", [sample_issue])

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
        cache.put("hash1", "rules1", "model-a", [new_issue])

        result = cache.get("hash1", "rules1", "model-a")
        assert len(result) == 1
        assert result[0].rule_id == "test/other"

    def test_clear_all(self, cache, sample_issue):
        """Should clear all cache entries."""
        cache.put("hash1", "rules1", "model-a", [sample_issue])
        cache.put("hash2", "rules1", "model-a", [sample_issue])

        deleted = cache.clear()

        assert deleted == 2
        assert cache.get("hash1", "rules1", "model-a") is None
        assert cache.get("hash2", "rules1", "model-a") is None

    def test_stats(self, cache, sample_issue):
        """Should return cache statistics."""
        cache.put("hash1", "rules1", "model-a", [sample_issue])
        cache.put("hash2", "rules1", "model-a", [sample_issue])

        stats = cache.stats()

        assert stats.entries == 2
        assert stats.size_bytes > 0


class TestRunLogging:
    """Tests for analysis run logging."""

    def test_log_run(self, cache):
        """Should log a run and return its ID."""
        run_id = cache.log_run(
            analyzer="agent",
            pack="django",
            files=["views.py"],
            duration_ms=1500,
            issues_found=3,
        )

        assert isinstance(run_id, str)
        assert run_id

    def test_get_runs(self, cache):
        """Should retrieve run logs."""
        cache.log_run(
            analyzer="agent",
            pack="django",
            files=["views.py"],
            duration_ms=1500,
            issues_found=3,
        )

        runs = cache.get_runs(limit=10)

        assert len(runs) == 1
        assert runs[0].analyzer == "agent"
        assert runs[0].pack == "django"
        assert runs[0].files == ["views.py"]
        assert runs[0].issues_found == 3

    def test_get_run_partial_match(self, cache):
        """Should find a run by ID prefix."""
        run_id = cache.log_run(
            analyzer="agent",
            pack="python",
            files=["a.py"],
            duration_ms=10,
            issues_found=0,
        )

        run = cache.get_run(run_id[:8])

        assert run is not None
        assert run.id == run_id


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

        # Verify data preserved: legacy llm_logs rows become run logs
        runs = cache.get_runs(limit=10)
        assert len(runs) == 1
        assert runs[0].analyzer == "gpt-4o-mini"
        assert runs[0].issues_found == 3

        # Verify the legacy table is replaced by runs
        conn = sqlite3.connect(db_path)
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "llm_logs" not in tables
        assert "runs" in tables

        # Verify version updated
        assert Migrator.get_version(conn) == SQLiteCache.CURRENT_VERSION
        conn.close()

    def test_migration_adds_analyzer_column(self, tmp_path):
        """Legacy cache entries survive the analyzer-column rebuild."""
        db_path = tmp_path / "legacy_cache.db"

        conn = sqlite3.connect(db_path)
        conn.executescript(_LEGACY_SCHEMA)
        conn.execute(
            "INSERT INTO cache (file_hash, rules_hash, issues_json) VALUES (?, ?, ?)",
            ("hash1", "rules1", "[]"),
        )
        conn.commit()
        conn.close()

        cache = SQLiteCache(db_path, ttl_hours=1)

        conn = sqlite3.connect(db_path)
        col_names = {row[1] for row in conn.execute("PRAGMA table_info(cache)").fetchall()}
        assert "analyzer" in col_names
        row = conn.execute("SELECT file_hash, analyzer FROM cache").fetchone()
        assert row == ("hash1", "")
        conn.close()

        # Legacy entries (analyzer='') never match real analyzer lookups
        assert cache.get("hash1", "rules1", "some-model") is None

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
