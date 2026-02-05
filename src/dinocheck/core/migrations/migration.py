"""Abstract base class for schema migrations."""

import sqlite3
from abc import ABC, abstractmethod


class Migration(ABC):
    """A single schema migration step."""

    @property
    @abstractmethod
    def version(self) -> int:
        """The version this migration upgrades TO (1-indexed)."""
        ...

    @abstractmethod
    def apply(self, conn: sqlite3.Connection) -> None:
        """Apply the migration to the database."""
        ...
