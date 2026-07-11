# CLAUDE.md

## Project Overview

Dinocheck is an agent-native code critic for vibe coding. It's a linter that reviews code semantically - not pattern matching. The host coding agent (Claude Code, Codex, Gemini CLI) performs the analysis via `dino brief` (files + rules + output contract) and `dino report` (validate, score, cache). Zero config: no API keys, no models, no external LLM calls.

## Key Commands

```bash
uv run dino brief --diff        # Step 1: emit review brief for the agent
uv run dino report results.json # Step 2: validate + score the agent's findings
uv run dino brief --debug       # Write detailed dino.log
uv run dino packs list          # List rule packs
uv run dino logs list           # View analysis run history
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
│   ├── issue_factory.py     # IssueFactory: findings -> Issue, filters, dedupe, limits
│   ├── config.py            # YAML + .env config loading
│   ├── cache.py             # SQLite cache (keyed per analyzer) + run logging
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
│       ├── analysis_log.py
│       ├── file_context.py
│       ├── diff_hunk.py
│       └── cache_stats.py
├── llm/
│   ├── schemas.py           # Pydantic output contract (AgentReport, CriticIssue)
│   └── prompts/
│       └── brief.py         # BriefBuilder for review briefs
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

- **Agent-native only**: The host coding agent performs all analysis (`dino brief` -> agent -> `dino report`). There is no API mode - dinocheck never calls an LLM itself. This decision is final.
- **LLM-first**: No pattern matching, pure semantic analysis
- **No fix command**: Linter only, doesn't modify code
- **Structured outputs**: The agent's findings are validated against Pydantic models
- **SQLite cache**: Avoids re-analyzing unchanged files (keyed per analyzer)
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
- `language`: Response language (en, es, fr, etc.)
- `packs`: Enabled rule packs (python, django); all enabled by default
- `exclude_packs` / `disabled_rules`: Opt out of packs or single rules
- `include_paths` / `exclude_paths`: Scope the analysis
- Custom rules: YAML files in `.dinocheck/rules/`

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
- One class per file (no multi-class files)
- Global imports (no local imports unless necessary)

## Refactoring Principles

- **No backwards compatibility aliases**: When refactoring, update all usages directly. Never create deprecated aliases or re-exports for backwards compatibility.
- **Prefer classes over loose functions**: Group related functionality into classes with clear responsibilities.
- **Update all callers**: When renaming or moving code, update all import statements and usages immediately.
