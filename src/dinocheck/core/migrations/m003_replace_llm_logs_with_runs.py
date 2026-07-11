"""Migration 003: Replace llm_logs with the analyzer-centric runs table."""

import sqlite3

from dinocheck.core.migrations.migration import Migration


class M003ReplaceLLMLogsWithRuns(Migration):
    """Rebuild call logging as run logging.

    With the removal of API mode there are no LLM calls, tokens, or costs
    to track - only analysis runs submitted by the host agent. Existing
    log rows are preserved (model becomes the analyzer identity); the
    token/cost columns are dropped with the old table.
    """

    @property
    def version(self) -> int:
        return 3

    def apply(self, conn: sqlite3.Connection) -> None:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "llm_logs" not in tables:
            return
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                analyzer TEXT NOT NULL,
                pack TEXT NOT NULL,
                files_json TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                issues_found INTEGER NOT NULL
            );
            INSERT OR IGNORE INTO runs
                (id, timestamp, analyzer, pack, files_json, duration_ms, issues_found)
                SELECT id, timestamp, model, pack, files_json, duration_ms, issues_found
                FROM llm_logs;
            DROP TABLE llm_logs;
            CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp);
            """
        )
