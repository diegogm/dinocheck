"""SQLite-based cache for analysis results and LLM call logging."""

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dinocheck.core.interfaces import Cache
from dinocheck.core.types import CacheStats, CostSummary, Issue, IssueLevel, LLMCallLog, Location

__all__ = ["SQLiteCache"]


class SQLiteCache(Cache):
    """SQLite-based persistent cache for analysis results and LLM logs."""

    SCHEMA = """
    -- Analysis cache table
    CREATE TABLE IF NOT EXISTS cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_hash TEXT NOT NULL,
        pack_version TEXT NOT NULL,
        rules_hash TEXT NOT NULL,
        issues_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(file_hash, pack_version, rules_hash)
    );
    CREATE INDEX IF NOT EXISTS idx_cache_created ON cache(created_at);
    CREATE INDEX IF NOT EXISTS idx_cache_lookup ON cache(file_hash, pack_version, rules_hash);

    -- LLM call logs table
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
    CREATE INDEX IF NOT EXISTS idx_llm_logs_timestamp ON llm_logs(timestamp);
    CREATE INDEX IF NOT EXISTS idx_llm_logs_model ON llm_logs(model);
    """

    def __init__(self, db_path: Path, ttl_hours: int = 168):
        self.db_path = db_path
        self.ttl_hours = ttl_hours
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure database and tables exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ==================== Cache Methods ====================

    def get(self, file_hash: str, pack_version: str, rules_hash: str) -> list[Issue] | None:
        """Get cached issues for a file if not expired."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT issues_json FROM cache
                   WHERE file_hash = ?
                   AND pack_version = ?
                   AND rules_hash = ?
                   AND created_at > datetime('now', ?)""",
                (file_hash, pack_version, rules_hash, f"-{self.ttl_hours} hours"),
            ).fetchone()

            if row:
                return self._deserialize_issues(row["issues_json"])
        return None

    def put(self, file_hash: str, pack_version: str, rules_hash: str, issues: list[Issue]) -> None:
        """Cache issues for a file."""
        issues_json = self._serialize_issues(issues)
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache
                   (file_hash, pack_version, rules_hash, issues_json, created_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (file_hash, pack_version, rules_hash, issues_json),
            )

    def clear(self, older_than_hours: int | None = None) -> int:
        """Clear cache entries, optionally older than threshold."""
        with self._connect() as conn:
            if older_than_hours:
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

    # ==================== LLM Logging Methods ====================

    def log_llm_call(
        self,
        model: str,
        pack: str,
        files: list[str],
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        issues_found: int,
        cost_usd: float | None = None,
        prompt_text: str | None = None,
        response_text: str | None = None,
        cached: bool = False,
    ) -> float:
        """Log an LLM call and return the cost in USD."""
        log_id = str(uuid.uuid4())

        # Calculate cost if not provided
        if cost_usd is None:
            cost_usd = self._estimate_cost(model, prompt_tokens, completion_tokens)

        with self._connect() as conn:
            conn.execute(
                """INSERT INTO llm_logs
                   (id, model, pack, files_json, prompt_tokens, completion_tokens,
                    total_tokens, cost_usd, duration_ms, issues_found, cached,
                    prompt_text, response_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    log_id,
                    model,
                    pack,
                    json.dumps(files),
                    prompt_tokens,
                    completion_tokens,
                    prompt_tokens + completion_tokens,
                    cost_usd,
                    duration_ms,
                    issues_found,
                    1 if cached else 0,
                    prompt_text,
                    response_text,
                ),
            )

        return cost_usd

    def get_llm_logs(self, limit: int = 20) -> list[LLMCallLog]:
        """Get recent LLM call logs."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, timestamp, model, pack, files_json,
                          prompt_tokens, completion_tokens, total_tokens,
                          cost_usd, duration_ms, issues_found, cached
                   FROM llm_logs
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

        return [
            LLMCallLog(
                id=row["id"],
                timestamp=row["timestamp"],
                model=row["model"],
                pack=row["pack"],
                files=json.loads(row["files_json"]),
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                total_tokens=row["total_tokens"],
                cost_usd=row["cost_usd"],
                duration_ms=row["duration_ms"],
                issues_found=row["issues_found"],
                cached=bool(row["cached"]),
            )
            for row in rows
        ]

    def get_llm_log(self, log_id: str) -> LLMCallLog | None:
        """Get a specific LLM call log by ID (partial match)."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT id, timestamp, model, pack, files_json,
                          prompt_tokens, completion_tokens, total_tokens,
                          cost_usd, duration_ms, issues_found, cached
                   FROM llm_logs
                   WHERE id LIKE ?
                   LIMIT 1""",
                (f"{log_id}%",),
            ).fetchone()

        if row:
            return LLMCallLog(
                id=row["id"],
                timestamp=row["timestamp"],
                model=row["model"],
                pack=row["pack"],
                files=json.loads(row["files_json"]),
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                total_tokens=row["total_tokens"],
                cost_usd=row["cost_usd"],
                duration_ms=row["duration_ms"],
                issues_found=row["issues_found"],
                cached=bool(row["cached"]),
            )
        return None

    def get_cost_summary(self, days: int = 30) -> CostSummary:
        """Get cost summary for the last N days."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT
                       COUNT(*) as total_calls,
                       COALESCE(SUM(total_tokens), 0) as total_tokens,
                       COALESCE(SUM(cost_usd), 0) as total_cost,
                       COALESCE(SUM(issues_found), 0) as total_issues
                   FROM llm_logs
                   WHERE timestamp > datetime('now', ?)""",
                (f"-{days} days",),
            ).fetchone()

        total_calls = row["total_calls"] or 0
        total_cost = row["total_cost"] or 0.0
        return CostSummary(
            total_calls=total_calls,
            total_tokens=row["total_tokens"] or 0,
            total_cost=total_cost,
            total_issues=row["total_issues"] or 0,
            avg_cost_per_call=total_cost / max(1, total_calls),
        )

    # ==================== Helper Methods ====================

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

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost based on model and token counts using litellm."""
        try:
            from litellm import cost_per_token

            prompt_cost, completion_cost = cost_per_token(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            return prompt_cost + completion_cost
        except Exception:
            # Fallback: return 0 if model pricing not found
            return 0.0
