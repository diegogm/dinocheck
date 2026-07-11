# CLAUDE.md

## Project Overview

Dinocheck is an LLM-powered code critic for vibe coding. It's a linter that reviews code semantically - not pattern matching. It has two modes:

- **agent (default)**: the host coding agent (Claude Code, Codex, Gemini CLI) performs the analysis via `dino brief` (files + rules + output contract) and `dino report` (validate, score, cache). Zero config, no API keys.
- **api**: `dino check` calls an LLM API directly (GPT, Claude, Ollama via LiteLLM). For CI/headless.

## Key Commands

```bash
uv run dino brief --diff       # Agent mode step 1: emit review brief
uv run dino report results.json # Agent mode step 2: validate + score findings
uv run dino check              # API mode: analyze code (requires mode: api)
uv run dino check --debug      # Analyze with detailed dino.log
uv run dino check -v           # Verbose progress output
uv run dino packs list         # List rule packs
uv run dino logs cost          # View LLM costs
fab test                       # Run tests
fab lint                       # Run linters (ruff + mypy)
fab check                      # Run all checks
fab predeploy                  # Pre-deployment checks (strict ruff + tests)
fab publish                    # Publish to PyPI (runs predeploy first)
```

## Architecture

```
src/dinocheck/
├── cli/
│   ├── main.py              # Typer CLI entry point
│   └── formatters/          # Output formatters (one per file)
│       ├── text_formatter.py
│       ├── json_formatter.py
│       └── jsonl_formatter.py
├── core/
│   ├── planner.py           # AnalysisPlanner: discovery, rule triggering, cache lookup
│   ├── engine.py            # API-mode executor (LLM calls over a plan)
│   ├── issue_factory.py     # IssueFactory: response -> Issue, filters, dedupe, limits
│   ├── config.py            # YAML + .env config loading (mode: agent|api)
│   ├── cache.py             # SQLite cache (keyed per analyzer) + LLM logging
│   ├── scoring.py           # Score calculation
│   ├── workspace.py         # Git diff integration
│   ├── interfaces.py        # Abstract base classes
│   ├── logging.py           # Debug logging to dino.log
│   └── types/               # Core types (one per file)
│       ├── issue.py
│       ├── issue_level.py
│       ├── location.py
│       ├── rule.py
│       ├── rule_trigger.py
│       ├── analysis_plan.py
│       ├── file_analysis_task.py
│       ├── analysis_result.py
│       ├── completion_result.py
│       ├── file_context.py
│       ├── diff_hunk.py
│       ├── llm_call_log.py
│       └── cache_stats.py
├── providers/
│   ├── litellm_provider.py  # LiteLLM integration (api mode)
│   └── mock.py              # Testing mock
├── llm/
│   ├── schemas.py           # Pydantic structured outputs + AgentReport contract
│   └── prompts/
│       ├── critic.py        # CriticPromptBuilder for api-mode prompts
│       └── brief.py         # BriefBuilder for agent-mode review briefs
├── skills/
│   ├── loader.py            # SkillTemplates: packaged agent skill templates
│   └── templates/           # claude.md / codex.md / gemini.md
├── utils/
│   ├── hashing.py           # ContentHasher for cache keys
│   └── languages.py         # LanguageDetector for code fences
└── packs/
    ├── loader.py            # Pack loading and composition
    ├── python/
    │   ├── pack.py          # Python pack class
    │   └── rules/           # YAML rule files
    └── django/
        ├── pack.py          # Django pack class
        └── rules/           # YAML rule files (organized by category)
            ├── orm/
            ├── transactions/
            ├── security/
            ├── drf/
            ├── migrations/
            └── testing/
```

## Test Structure

Tests mirror the source structure:

```
tests/
├── unit/
│   ├── core/
│   │   ├── test_cache.py
│   │   ├── test_config.py
│   │   ├── test_scoring.py
│   │   └── test_workspace.py
│   └── packs/
│       └── test_loader.py
└── integration/
    ├── core/
    │   └── test_engine.py
    └── cli/
        └── test_cli.py
```

## Design Decisions

- **Agent-first**: Default mode delegates analysis to the host coding agent (`dino brief` -> agent -> `dino report`); the API mode is the fallback for CI
- **LLM-first**: No pattern matching, pure LLM analysis
- **No fix command**: Linter only, doesn't modify code
- **Structured outputs**: All LLM responses use Pydantic models
- **SQLite cache**: Avoids re-analyzing unchanged files
- **LiteLLM**: Unified interface to 100+ LLM providers
- **Vibe coding**: Designed for AI-assisted development workflows
- **YAML rules**: All rules defined in YAML files (no hardcoded rules in Python)
- **One class per file**: Types, formatters, and rules are each in separate files

## Rule Packs

Rules are YAML files in `packs/<pack>/rules/`:

```yaml
id: django/n-plus-one
name: N+1 Query Detection
level: major
category: performance
description: |
  Detects patterns that cause N+1 database queries.
triggers:
  file_patterns:
    - "**/views.py"
  code_patterns:
    - "for .+ in .+\\.objects\\."
checklist:
  - Loop iterating over queryset result
fix: Use select_related() for ForeignKey/OneToOne fields.
tags:
  - performance
  - orm
```

## Configuration

`dino.yaml` or `.env`:
- `mode`: `agent` (default, host agent analyzes) or `api` (direct LLM calls)
- `model`: LLM model for api mode (gpt-4o-mini, claude-3-5-sonnet, ollama/llama3)
- `language`: Response language (en, es, fr, etc.)
- `packs`: Enabled rule packs (python, django)
- `custom_rules_dir`: Directory for custom YAML rules

## Testing

```bash
fab test           # Run all tests
fab test --cov     # With coverage
fab ci             # Full CI pipeline
```

## Code Style

- Python 3.11+
- Ruff for linting/formatting
- Mypy strict mode
- Async/await for LLM calls
- One class per file (no multi-class files)
- Global imports (no local imports unless necessary)

## Refactoring Principles

- **No backwards compatibility aliases**: When refactoring, update all usages directly. Never create deprecated aliases or re-exports for backwards compatibility.
- **Prefer classes over loose functions**: Group related functionality into classes with clear responsibilities.
- **Update all callers**: When renaming or moving code, update all import statements and usages immediately.
