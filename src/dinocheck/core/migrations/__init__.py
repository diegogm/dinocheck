"""Schema migrations for the SQLite cache database."""

from dinocheck.core.migrations.m001_drop_prompt_response import M001DropPromptResponse
from dinocheck.core.migrations.m002_add_analyzer_column import M002AddAnalyzerColumn
from dinocheck.core.migrations.m003_replace_llm_logs_with_runs import M003ReplaceLLMLogsWithRuns
from dinocheck.core.migrations.migration import Migration
from dinocheck.core.migrations.migrator import Migrator

MIGRATIONS: tuple[Migration, ...] = (
    M001DropPromptResponse(),
    M002AddAnalyzerColumn(),
    M003ReplaceLLMLogsWithRuns(),
)

__all__ = [
    "MIGRATIONS",
    "Migration",
    "Migrator",
]
