# Configuration

Dinocheck can be configured via `dino.yaml` or environment variables.

Dinocheck is agent-native: your AI coding agent performs the review via
`dino brief` + `dino report`, so there is nothing to configure for LLM
access - no providers, no models, no API keys.

## Configuration File

Create a `dino.yaml` in your project root:

```bash
dino init
```

### Full Example

```yaml
# Response language (en, es, fr, de, etc.)
language: en

# Exclude packs you don't need (all enabled by default)
exclude_packs:
  - vue
  - docker

# Or explicitly enable only specific packs
# packs:
#   - python
#   - django

# Analyze only specific directories (default: current directory)
# include_paths:
#   - src/
#   - lib/

# Exclude paths from analysis (glob patterns)
exclude_paths:
  - migrations
  - tests/fixtures

# Disable specific rules
disabled_rules:
  - python/broad-exception
```

## Path Filtering

### Include Paths

Specify default directories to analyze (when no paths are given via CLI):

```yaml
include_paths:
  - src/
  - lib/
```

When `include_paths` is set, `dino brief` will only scan those directories by default.
CLI paths override this setting: `dino brief other/` will ignore `include_paths`.

### Exclude Paths

Exclude files or directories from analysis using glob patterns:

```yaml
exclude_paths:
  - migrations
  - tests/fixtures
  - "*.generated.py"
```

Patterns are matched against directory names and file paths:
- `migrations` — excludes any directory named `migrations`
- `tests/fixtures` — excludes the `tests/fixtures` path
- `*.generated.py` — excludes files matching the pattern

These work alongside the built-in exclusions (hidden directories, `__pycache__`,
`node_modules`, `.venv`, `venv`).

## Environment Variables

You can override config values via environment variables with the `DINO_` prefix:

```bash
export DINO_LANGUAGE=es
```

## Configuration Priority

Settings are loaded in this order (highest priority first):

1. Environment variables (`DINO_LANGUAGE`)
2. `.env` file (in same directory as `dino.yaml`)
3. `dino.yaml`
4. Default values
