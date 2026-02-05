"""Schema version management and migration runner."""

import sqlite3

from dinocheck.core.migrations.migration import Migration


class Migrator:
    """Manages schema version and applies pending migrations via PRAGMA user_version."""

    def __init__(self, migrations: tuple[Migration, ...]) -> None:
        self._migrations = migrations

    @staticmethod
    def get_version(conn: sqlite3.Connection) -> int:
        row = conn.execute("PRAGMA user_version").fetchone()
        return int(row[0])

    @staticmethod
    def set_version(conn: sqlite3.Connection, version: int) -> None:
        conn.execute(f"PRAGMA user_version = {version}")

    def apply_pending(self, conn: sqlite3.Connection, target: int) -> None:
        current = self.get_version(conn)
        if target > len(self._migrations):
            raise ValueError(
                f"Target version {target} exceeds available migrations ({len(self._migrations)})"
            )
        if target < current:
            raise ValueError(f"Downgrade from version {current} to {target} is not supported")
        for i in range(current, target):
            self._migrations[i].apply(conn)
        self.set_version(conn, target)
