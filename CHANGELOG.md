# Changelog

All notable changes to Dinocheck will be documented in this file.

## [0.2.0] - 2026-07-11

Dinocheck is now **agent-native only**. The host coding agent (Claude Code,
Codex, Gemini CLI) performs the analysis; dinocheck never calls an LLM API.
This decision is final - there is no API mode and none is planned.

### Added
- **Full rule pack review**: all 125 rules audited and improved - clearer
  descriptions, evaluable checklists, actionable fix guidance, bad/good
  examples everywhere, and corrected trigger regexes (several were inert:
  `^`/`$` anchors never match mid-file without MULTILINE, `.` never crosses
  newlines). Rule quality is now enforced by ~750 per-rule tests, including
  the invariant that each rule's own bad example trips its trigger
- **Multi-language analysis**: discovery is driven by the enabled packs'
  file patterns instead of being hardcoded to `*.py` - react, vue, css,
  docker, compose, shell, and latex files are now actually discovered,
  both in directory scans and in `--diff` mode
- **Changed-line focus**: in `--diff` mode the brief marks each file's
  changed line ranges ("Changed lines: 6-10") or flags it as a new file,
  and instructs the agent to focus its review there
- **Anti-hallucination validation** in `dino report`: findings citing rules
  not in the file's rule list are dropped with a warning; findings pointing
  outside the file's line range are dropped; overshot end lines are clamped
- `dino report --fail-on LEVEL`: exit 1 when issues at or above the given
  severity survive validation (CI gating)
- `dino init` adds `.dinocheck/` to `.gitignore`
- **Agent-native analysis**: the host coding agent performs the review
  itself - zero config, no API keys
  - `dino brief`: emits a review brief (files, triggered rules with full
    checklists/examples, output contract) for the agent; `--diff`,
    `--format json`, `--embed-code`, `--debug`
  - `dino report`: validates the agent's findings against the output contract
    (precise, retryable errors), converts, dedupes, scores, caches, and formats
- Agent skill templates shipped as package data (`dinocheck/skills/templates/`)
  and used by `dino skill` / `dino init`; skills document the
  brief/analyze/report workflow
- Cache entries are keyed per analyzer so results never mix; schema
  migration 002 rebuilds the cache table
- Analysis run history: `dino logs list` / `dino logs show` record each
  submitted report (schema migration 003)
- `AnalysisPlanner` (discovery, rule triggering, cache lookup) and
  `IssueFactory` (findings conversion, filters, dedupe, limits) as the
  deterministic core
- Invalid findings (e.g. bad severity level) are surfaced as warnings
  instead of silently dropped

### Fixed
- `**/x` rule patterns now match root-level files: a repo-root `Dockerfile`,
  `docker-compose.yml`, or `views.py` previously never triggered any rule
- React pack rules now trigger on `.tsx` files (previously `.jsx` only)
- Cache keys use rule content fingerprints, so editing a rule's checklist,
  fix, examples, or severity invalidates stale cached results
- Files larger than 1 MB are skipped with a warning instead of being sent
  to the analyzer
- `--diff` briefs use cwd-relative paths instead of absolute paths

### Removed
- **API mode, entirely**: the `Engine`, the `providers/` package (LiteLLM),
  the `dino check` command, and the `mode`, `model`, `base_url`, and
  `max_llm_calls` config options. Legacy keys in existing `dino.yaml`
  files are ignored.
- Cost and token tracking (`dino logs cost`, per-call token counts): with no
  API calls there is nothing to meter. Existing log rows are preserved as
  run history.
- Dependencies: `litellm`, `httpx`, `aiofiles`, `pytest-asyncio`
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
