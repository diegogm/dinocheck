"""Migration 002: Add analyzer identity to the cache key."""

import sqlite3

from dinocheck.core.migrations.migration import Migration


class M002AddAnalyzerColumn(Migration):
    """Rebuild the cache table with an analyzer column in the unique key.

    Results produced by different analyzers (an API model or the host
    agent) must not collide in the cache. Existing entries predate the
    column and are kept under the empty analyzer '' - they simply stop
    matching lookups and expire via TTL.
    """

    @property
    def version(self) -> int:
        return 2

    def apply(self, conn: sqlite3.Connection) -> None:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(cache)").fetchall()}
        if "analyzer" in existing:
            return
        conn.executescript(
            """
            CREATE TABLE cache_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                rules_hash TEXT NOT NULL,
                analyzer TEXT NOT NULL DEFAULT '',
                issues_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(file_hash, rules_hash, analyzer)
            );
            INSERT INTO cache_v2 (id, file_hash, rules_hash, analyzer, issues_json, created_at)
                SELECT id, file_hash, rules_hash, '', issues_json, created_at FROM cache;
            DROP TABLE cache;
            ALTER TABLE cache_v2 RENAME TO cache;
            CREATE INDEX IF NOT EXISTS idx_cache_created ON cache(created_at);
            """
        )
