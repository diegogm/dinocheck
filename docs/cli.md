# CLI Reference

## Main Commands

### `dino check`

Analyze code with LLM.

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
| `dino check [paths]` | Analyze code with LLM |
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
