# Plan: Agent-Native Mode (zero-config, host-model analysis)

**Status:** Proposed
**Goal:** Remove the hard dependency on an external LLM API. When dinocheck runs
inside an AI coding agent (Claude Code, Codex, Gemini CLI), the *host model
itself* performs the analysis. Dinocheck's job becomes: select files, select
rules, produce a precise review brief, then validate/score/cache the results
the agent produces. Zero configuration, zero API keys → much lower adoption
friction.

---

## 1. Concept

Today the pipeline is:

```
discover files → match rules → cache check → [LiteLLM call per file] → issues → score → format
```

The proposal splits the pipeline at the LLM boundary and exposes both halves
as CLI commands, so any host agent can be the "executor" in the middle:

```
dino brief   →  (host model analyzes)  →  dino report
─────────────                             ──────────────
discover files                            validate JSON against schema
match rules per file                      convert to Issue objects
cache check                               dedupe + limit + score
emit review brief                         write cache
                                          format (text/json/jsonl)
```

Everything deterministic stays in dinocheck (triggers, cache, scoring,
dedup, formatting). Only the semantic judgment moves to the host model.

Key insight: **the brief does not need to embed file contents.** The host
agent already has file access — the brief lists file paths, the full text of
each applicable rule (description, checklist, fix, examples), and the exact
output contract. This keeps the brief small even for large changesets. An
`--embed-code` flag covers agents without filesystem access.

## 2. Why this shape (alternatives considered)

- **A. Two-command CLI handshake (`brief`/`report`) — chosen.** Agent-agnostic
  (works identically for Claude/Codex/Gemini skills), preserves cache/score/
  dedup/formatters, fully testable without any model.
- **B. Pure skill (ship rules inside SKILL.md, no CLI).** Zero install, but
  loses cache, scoring, triggers, dedup, and 135 rules don't fit in a skill
  context. Rejected.
- **C. MCP server.** Requires server registration per agent → reintroduces the
  configuration burden the feature is meant to remove. Rejected for now; the
  CLI handshake doesn't preclude adding MCP later on top of the same planner.

**API mode stays as a secondary path** (config `mode: api`) because headless
environments (CI) have no host model. Default behavior: `mode: agent`. This is
a product decision that can be revisited — if API mode is dropped entirely,
delete `providers/`, `max_llm_calls`, cost tracking, and the ThreadPool
executor in a follow-up.

## 3. Refactor: split the Engine

`Engine.analyze()` (engine.py:70) currently interleaves planning and
execution. Extract:

- **`core/planner.py` — `AnalysisPlanner`**: steps 0–3 of today's
  `analyze()` (include_paths, pack composition, discovery, rule triggering,
  rule_filter, cache lookup). Returns an `AnalysisPlan`.
- **`core/types/analysis_plan.py` — `AnalysisPlan`**: `tasks:
  list[FileAnalysisTask]`, `cached_issues: list[Issue]`, counters
  (skipped/cached/pending).
- **`core/types/file_analysis_task.py` — `FileAnalysisTask`**: `file_ctx`,
  `rules`, `file_hash`, `rules_hash`.
- **`core/issue_factory.py` — `IssueFactory`**: today's
  `Engine._response_to_issues` + `_deduplicate` + `_limit_per_file`
  (engine.py:387-455), shared by both modes.
- **`Engine`** becomes the API-mode executor: consumes an `AnalysisPlan`,
  runs the ThreadPool + LiteLLM loop, delegates to `IssueFactory` and
  `ScoreCalculator`.

Per CLAUDE.md refactoring principles: no compatibility aliases, update all
callers, one class per file.

## 4. New commands

### `dino brief [PATHS] [--diff] [--format markdown|json] [--embed-code] [-o FILE]`

Runs `AnalysisPlanner`, emits the brief for pending (uncached) tasks:

- Header: output contract — per-file JSON matching `CriticResponse`
  (llm/schemas.py), the confidence bar (≥0.8), the "don't invent rules"
  guidance (reuse the content of today's `SYSTEM_TEMPLATE`).
- Per file: path, line count, `file_hash`, and the full text of each
  triggered rule (description, checklist, fix, examples — today's prompt only
  sends `description[:100]`, see critic.py:85; the brief fixes that).
- Footer: cached results summary + the exact `dino report` invocation to run.
- New `llm/prompts/brief.py` — `BriefBuilder` (mirrors `CriticPromptBuilder`).
- Exit 0 with "nothing to analyze" when all files are cached/skipped.

### `dino report RESULTS.json [--format text|json|jsonl] [-o FILE]`

- Input: `{ "files": [ { "path": ..., "issues": [CriticIssue...] } ] }`,
  validated with the existing Pydantic schemas → invalid input yields precise,
  machine-readable errors so the agent can self-correct and retry.
- Recomputes `file_hash` at report time; a file changed since the brief is
  cached under its *current* hash (content is hashed from disk), and a
  missing file is reported as an error for that entry.
- Pipeline: `IssueFactory` → disabled_rules filter → dedupe → limit →
  `ScoreCalculator` → cache `put` → existing formatters.
- Logs the run via `cache.log_llm_call` with `model="agent"` and
  `cost_usd=0.0` so `dino logs` keeps working.

## 5. Config & validation changes

- `DinocheckConfig.mode: Literal["agent", "api"] = "agent"`.
- `ConfigManager.validate()` (config.py:149) only checks the API key when
  `mode == "api"` — this is the blocker for zero-config today.
- `dino check` in agent mode prints a pointer to `dino brief` / the skill
  instead of failing with a missing-key error.
- `dino init` template: agent mode by default; `model:` becomes an opt-in
  comment under an "API mode (CI)" section.

## 6. Skill rewrite (the integration surface)

The three near-identical inline skill strings in `cli/main.py:699-868` move to
package data templates (`src/dinocheck/skills/templates/{claude,codex,gemini}/SKILL.md`)
loaded by `dino skill` / `dino init`. New skill workflow:

```
1. dino brief --diff -o .dinocheck/brief.md   (or PATHS the user asked about)
2. Read the brief. For each file: open it, evaluate ONLY the listed rules
   using their checklists. Follow the output contract exactly.
3. Write results to .dinocheck/results.json
4. dino report .dinocheck/results.json
5. Present the formatted output; fix nothing unless asked.
```

`allowed-tools: Bash(dino:*)` stays. The repo's own
`.claude/skills/dinocheck/SKILL.md` is regenerated from the new template.

## 7. Cache correctness (pre-existing gap, becomes critical)

The cache key is `(file_hash, rules_hash)` only — results from different
models (or agent vs API mode) collide. Add the analyzer identity
(`model` string or `"agent"`) to the key via a new column + migration
`m002_add_analyzer_column` (migrations framework already exists).

## 8. Bugs & cleanups to fix along the way

Found during the review; several become load-bearing for agent mode:

1. **engine.py:267** — `raise` inside the `as_completed` loop aborts the whole
   run on a single file failure, discarding completed results. Collect errors,
   continue, surface at the end.
2. **critic.py:49** — code fence hardcoded to ```` ```python ```` for all
   packs (react/latex packs exist). Derive from file extension.
3. **critic.py:71** — silent 10,000-char truncation of file content; at
   minimum, log/annotate it. Agent mode sidesteps this (no embedding).
4. **engine.py:424** — `except Exception: continue` silently drops issues the
   LLM returned (e.g. an invalid `level` string). Log at warning level; in
   `dino report`, surface as validation errors instead.
5. **engine.py:214** — files beyond `max_llm_calls` are silently dropped;
   report the truncation in `meta`/output.
6. **engine.py:366** — `CriticResponse.model_validate(result.model_dump())`
   re-validates an already-validated model. Remove.
7. **engine.py:28** — `MAX_TOKENS_PER_CALL` is defined but never used.
8. **engine.py:375-382** — cost computed from `estimate_tokens` instead of the
   actual `usage` returned by LiteLLM. Fix in API mode; moot in agent mode.
9. **interfaces.py:16** — `Analyzer` ABC ("ruff, mypy") is dead code and
   contradicts the LLM-first design decision. Delete.
10. **cli/main.py** — `check` mixes CLI parsing with progress-string re-parsing
    (splitting `" → "` strings it built itself); pass structured progress
    events instead. Low priority.

## 9. Phases

| Phase | Work | Size |
|---|---|---|
| 1 | Engine split: `AnalysisPlanner`, `AnalysisPlan`, `FileAnalysisTask`, `IssueFactory`; `Engine` consumes the plan. Fixes #1, #6, #7, #9. Tests for planner. | ~1 day |
| 2 | Cache analyzer-identity column + migration `m002`. | ~0.5 day |
| 3 | `dino brief` (`BriefBuilder`) + `dino report` with schema validation, hashing, scoring, cache write. Fixes #4. Integration tests with fixture JSON (no LLM needed). | ~1–1.5 days |
| 4 | Config `mode`, validation gating, `dino init` template. Fixes zero-config blocker. | ~0.5 day |
| 5 | Skill templates as package data, rewrite content for brief/report loop, regenerate repo skill, `dino skill` reads templates. | ~0.5 day |
| 6 | Docs (README, getting-started, integrations, CLAUDE.md architecture), CHANGELOG. Remaining cleanups (#2, #3, #5, #8). | ~0.5 day |

Total ≈ 4–5 days of focused work. Phases 1–3 are the core; 4–6 polish.

## 10. Risks

- **No structured-output enforcement on the host model.** Mitigation: `dino
  report` is a strict validator with actionable errors; agents retry cheaply.
- **Result variability across host models.** Same as today across API models;
  the checklist-driven rules keep judgments anchored.
- **File drift between brief and report.** Hashes recomputed at report time;
  cache never stores stale associations.
- **CI/headless.** Covered by keeping `mode: api`.
- **Score comparability** between agent and API runs. The analyzer-identity
  cache column keeps them from cross-contaminating; document that scores are
  per-analyzer.
