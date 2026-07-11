# Changelog

All notable changes to Dinocheck will be documented in this file.

## [Unreleased]

### Added
- **Agent-native mode (new default)**: the host coding agent (Claude Code,
  Codex, Gemini CLI) performs the analysis itself - zero config, no API keys
  - `dino brief`: emits a review brief (files, triggered rules with full
    checklists/examples, output contract) for the agent; `--diff`,
    `--format json`, `--embed-code`
  - `dino report`: validates the agent's findings against the output contract
    (precise, retryable errors), converts, dedupes, scores, caches, and formats
- `mode: agent|api` config option (`DINO_MODE` env var); API key validation
  only applies to api mode
- Agent skill templates shipped as package data (`dinocheck/skills/templates/`)
  and used by `dino skill` / `dino init`; skills now document the
  brief/analyze/report workflow
- Cache entries are keyed per analyzer (model or agent) so results never mix;
  schema migration 002 rebuilds the cache table

### Changed
- Engine split: `AnalysisPlanner` (discovery, rule triggering, cache lookup)
  and `IssueFactory` (issue conversion, filters, dedupe, limits) extracted
  from the engine and shared by both modes
- `dino check` now requires `mode: api`; in agent mode it points to the
  brief/report workflow
- One failed LLM call no longer aborts the whole `dino check` run; errors are
  collected and reported in `meta.errors`
- LLM cost/token accounting uses the provider-reported usage when available
- Prompt code fences use the file's language (previously hardcoded to python)
- Files dropped by the `max_llm_calls` budget or by content truncation are
  now reported instead of silently skipped
- Invalid issues returned by the LLM/agent (e.g. bad severity level) are
  surfaced as warnings instead of silently dropped

### Removed
- Unused `Analyzer` abstract base class

## [0.1.0] - 2026-01-04

### Added
- Initial release of Dinocheck - LLM-powered code critic
- Python pack with 25 semantic rules
- Django pack with 22 rules for Django/DRF projects
- Text, JSON, and JSONL output formatters
- SQLite-based caching for analysis results
- LLM call logging and cost tracking
- Debug mode with detailed logging (`--debug`)
- Progress callbacks for verbose mode (`-v`)
- Colored terminal output using Rich

### Features
- **Rule packs**: Modular rule system with Python and Django packs
- **Multi-provider support**: OpenAI, Anthropic, Ollama via LiteLLM
- **Smart caching**: Content-addressed cache to avoid re-analyzing unchanged files
- **Git integration**: `--diff` flag to only analyze changed files
- **Cost tracking**: Track LLM usage and costs with `dino logs cost`

### Commands
- `dino check` - Analyze code with LLM-powered critique
- `dino packs list` - List available rule packs
- `dino packs info <pack>` - Show pack details and rules
- `dino explain <rule>` - Explain a specific rule
- `dino cache stats` - Show cache statistics
- `dino logs list` - View recent LLM calls
- `dino logs cost` - View cost summary
- `dino init` - Initialize configuration file

### Configuration
- YAML-based configuration (`dino.yaml`)
- Environment variable overrides (`DINO_MODEL`, `DINO_LANGUAGE`)
- Configurable packs, model, language, and budget
