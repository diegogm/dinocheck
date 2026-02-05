"""Schema migrations for the SQLite cache database."""

from dinocheck.core.migrations.m001_drop_prompt_response import M001DropPromptResponse
from dinocheck.core.migrations.migration import Migration
from dinocheck.core.migrations.migrator import Migrator

MIGRATIONS: tuple[Migration, ...] = (M001DropPromptResponse(),)

__all__ = [
    "MIGRATIONS",
    "Migration",
    "Migrator",
]
