"""Migration 001: Remove prompt_text and response_text from llm_logs."""

import sqlite3

from dinocheck.core.migrations.migration import Migration


class M001DropPromptResponse(Migration):
    """Drop prompt_text and response_text columns from llm_logs table."""

    @property
    def version(self) -> int:
        return 1

    def apply(self, conn: sqlite3.Connection) -> None:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(llm_logs)").fetchall()}
        for col in ("prompt_text", "response_text"):
            if col in existing:
                conn.execute(f"ALTER TABLE llm_logs DROP COLUMN {col}")
