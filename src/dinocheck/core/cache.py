"""SQLite-based cache for analysis results and run logging."""

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dinocheck.core.interfaces import Cache
from dinocheck.core.migrations import MIGRATIONS, Migrator
from dinocheck.core.types import AnalysisLog, CacheStats, Issue, IssueLevel, Location

__all__ = ["SQLiteCache"]


class SQLiteCache(Cache):
    """SQLite-based persistent cache for analysis results and run logs."""

    SCHEMA = """
    -- Analysis cache table
    CREATE TABLE IF NOT EXISTS cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_hash TEXT NOT NULL,
        rules_hash TEXT NOT NULL,
        analyzer TEXT NOT NULL DEFAULT '',
        issues_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(file_hash, rules_hash, analyzer)
    );
    CREATE INDEX IF NOT EXISTS idx_cache_created ON cache(created_at);

    -- Analysis run logs table
    CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        analyzer TEXT NOT NULL,
        pack TEXT NOT NULL,
        files_json TEXT NOT NULL,
        duration_ms INTEGER NOT NULL,
        issues_found INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp);
    """

    CURRENT_VERSION = 3

    def __init__(self, db_path: Path, ttl_hours: int = 168):
        self.db_path = db_path
        self.ttl_hours = ttl_hours
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure database and tables exist, applying pending migrations."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        migrator = Migrator(MIGRATIONS)
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
            current = migrator.get_version(conn)
            if current < self.CURRENT_VERSION:
                migrator.apply_pending(conn, self.CURRENT_VERSION)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
        finally:
            conn.close()

    # ==================== Cache Methods ====================

    def get(self, file_hash: str, rules_hash: str, analyzer: str) -> list[Issue] | None:
        """Get cached issues for a file if not expired."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT issues_json FROM cache
                   WHERE file_hash = ?
                   AND rules_hash = ?
                   AND analyzer = ?
                   AND created_at > datetime('now', ?)""",
                (file_hash, rules_hash, analyzer, f"-{self.ttl_hours} hours"),
            ).fetchone()

            if row:
                return self._deserialize_issues(row["issues_json"])
        return None

    def put(self, file_hash: str, rules_hash: str, analyzer: str, issues: list[Issue]) -> None:
        """Cache issues for a file."""
        issues_json = self._serialize_issues(issues)
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache
                   (file_hash, rules_hash, analyzer, issues_json, created_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (file_hash, rules_hash, analyzer, issues_json),
            )

    def clear(self, older_than_hours: int | None = None) -> int:
        """Clear cache entries, optionally older than threshold."""
        with self._connect() as conn:
            if older_than_hours is not None:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE created_at < datetime('now', ?)",
                    (f"-{older_than_hours} hours",),
                )
            else:
                cursor = conn.execute("DELETE FROM cache")
            return cursor.rowcount

    def stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]

            oldest = conn.execute("SELECT MIN(created_at) FROM cache").fetchone()[0]

            newest = conn.execute("SELECT MAX(created_at) FROM cache").fetchone()[0]

        size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return CacheStats(
            entries=total,
            size_bytes=size,
            oldest_entry=oldest,
            newest_entry=newest,
        )

    # ==================== Run Logging Methods ====================

    def log_run(
        self,
        analyzer: str,
        pack: str,
        files: list[str],
        duration_ms: int,
        issues_found: int,
    ) -> str:
        """Log an analysis run and return its ID."""
        run_id = str(uuid.uuid4())

        with self._connect() as conn:
            conn.execute(
                """INSERT INTO runs
                   (id, analyzer, pack, files_json, duration_ms, issues_found)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    analyzer,
                    pack,
                    json.dumps(files),
                    duration_ms,
                    issues_found,
                ),
            )

        return run_id

    def get_runs(self, limit: int = 20) -> list[AnalysisLog]:
        """Get recent analysis run logs."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, timestamp, analyzer, pack, files_json,
                          duration_ms, issues_found
                   FROM runs
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

        return [self._row_to_log(row) for row in rows]

    def get_run(self, run_id: str) -> AnalysisLog | None:
        """Get a specific analysis run log by ID (partial match)."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT id, timestamp, analyzer, pack, files_json,
                          duration_ms, issues_found
                   FROM runs
                   WHERE id LIKE ?
                   LIMIT 1""",
                (f"{run_id}%",),
            ).fetchone()

        if row:
            return self._row_to_log(row)
        return None

    # ==================== Helper Methods ====================

    @staticmethod
    def _row_to_log(row: sqlite3.Row) -> AnalysisLog:
        """Convert a runs row to an AnalysisLog."""
        return AnalysisLog(
            id=row["id"],
            timestamp=row["timestamp"],
            analyzer=row["analyzer"],
            pack=row["pack"],
            files=json.loads(row["files_json"]),
            duration_ms=row["duration_ms"],
            issues_found=row["issues_found"],
        )

    def _serialize_issues(self, issues: list[Issue]) -> str:
        """Serialize issues to JSON."""
        return json.dumps([self._issue_to_dict(i) for i in issues])

    def _deserialize_issues(self, json_str: str) -> list[Issue]:
        """Deserialize issues from JSON."""
        data = json.loads(json_str)
        return [self._dict_to_issue(d) for d in data]

    def _issue_to_dict(self, issue: Issue) -> dict[str, Any]:
        """Convert Issue to dictionary for serialization."""
        return {
            "rule_id": issue.rule_id,
            "level": str(issue.level),
            "location": {
                "path": str(issue.location.path),
                "start_line": issue.location.start_line,
                "end_line": issue.location.end_line,
                "start_col": issue.location.start_col,
                "end_col": issue.location.end_col,
            },
            "title": issue.title,
            "why": issue.why,
            "do": issue.do,
            "pack": issue.pack,
            "source": issue.source,
            "confidence": issue.confidence,
            "tags": issue.tags,
        }

    def _dict_to_issue(self, d: dict[str, Any]) -> Issue:
        """Convert dictionary to Issue."""
        return Issue(
            rule_id=d["rule_id"],
            level=IssueLevel(d["level"]),
            location=Location(
                path=Path(d["location"]["path"]),
                start_line=d["location"]["start_line"],
                end_line=d["location"].get("end_line"),
                start_col=d["location"].get("start_col"),
                end_col=d["location"].get("end_col"),
            ),
            title=d["title"],
            why=d["why"],
            do=d["do"],
            pack=d["pack"],
            source=d["source"],
            confidence=d.get("confidence", 1.0),
            tags=d.get("tags", []),
        )
