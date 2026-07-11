# CLI Reference

## Main Commands

### `dino brief`

Generate a review brief for the host coding agent (agent mode, step 1).
Selects files and matching rules and emits the instructions the agent needs
to perform the analysis itself. No LLM API is called.

```bash
# Brief for changed files (preferred in the skill workflow)
dino brief --diff -o .dinocheck/brief.md

# Brief for specific paths
dino brief src/

# Machine-readable brief
dino brief --format json

# Embed file contents (for agents without file access)
dino brief --embed-code

# Restrict packs or rules
dino brief --pack django
dino brief --rule n-plus-one
```

### `dino report`

Validate and score the agent's findings (agent mode, step 2). Reads the
results JSON produced from a brief, validates it against the output contract,
deduplicates, scores, caches, and prints the formatted result.

```bash
dino report .dinocheck/results.json
dino report results.json --format json
dino report results.json -o review.txt
```

Validation problems are reported precisely (exit code 2) so the agent can fix
the JSON and retry.

### `dino check`

Analyze code by calling an LLM API directly. Requires `mode: api` in
`dino.yaml` and an API key; in agent mode it points you to
`dino brief` / `dino report` instead.

```bash
# Analyze current directory
dino check

# Analyze specific files
dino check src/views.py src/models.py

# Analyze with options
dino check --diff           # Only changed files
dino check -v               # Verbose output
dino check --debug          # Debug logging to dino.log
dino check --no-cache       # Skip cache
dino check --format json    # JSON output
dino check --format jsonl   # JSON Lines output
```

### `dino init`

Create a `dino.yaml` configuration file.

```bash
dino init
```

If agent folders (`.claude`, `.codex`, `.gemini`) exist, it will offer to create skills.

### `dino skill`

Create agent skills for AI coding assistants.

```bash
# Auto-detect and create for all agents
dino skill

# Create for specific agent
dino skill --agent claude
dino skill --agent codex
dino skill --agent gemini

# Force overwrite existing
dino skill --force
```

See [Coding Agents](integrations.md) for full documentation.

### `dino version`

Show version information.

```bash
dino version
```

## Pack Commands

### `dino packs list`

List all available rule packs.

```bash
dino packs list
```

### `dino packs info`

Show details of a specific pack.

```bash
dino packs info python
dino packs info django
```

### `dino explain`

Explain a specific rule.

```bash
dino explain django/n-plus-one
dino explain python/mutable-default
```

## Cache Commands

### `dino cache stats`

Show cache statistics.

```bash
dino cache stats
```

### `dino cache clear`

Clear the analysis cache.

```bash
dino cache clear
```

## Log Commands

### `dino logs list`

View LLM call history.

```bash
dino logs list
```

### `dino logs show`

Show details of a specific LLM call.

```bash
dino logs show 123
```

### `dino logs cost`

View cost summary.

```bash
dino logs cost
```

## Command Summary

| Command | Description |
|---------|-------------|
| `dino brief [paths]` | Generate a review brief for the host agent |
| `dino brief --diff` | Brief covering only changed files |
| `dino brief --embed-code` | Include file contents in the brief |
| `dino report FILE` | Validate, score, and cache agent findings |
| `dino check [paths]` | Analyze code with LLM API (api mode) |
| `dino check --diff` | Analyze only changed files |
| `dino check -v` | Verbose output with progress |
| `dino check --debug` | Enable debug logging to dino.log |
| `dino check --no-cache` | Skip cache, re-analyze all files |
| `dino packs list` | List available packs |
| `dino packs info NAME` | Show pack details |
| `dino explain RULE_ID` | Explain a rule |
| `dino cache stats` | Show cache statistics |
| `dino cache clear` | Clear the cache |
| `dino logs list` | View LLM call history |
| `dino logs show ID` | Show details of a specific LLM call |
| `dino logs cost` | View cost summary |
| `dino init` | Create dino.yaml |
| `dino skill` | Create agent skills |
| `dino skill --agent NAME` | Create skill for specific agent |
| `dino version` | Show version information |
