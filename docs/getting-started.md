# Getting Started

## Installation

```bash
pip install dinocheck
# or with uv
uv add dinocheck
```

## Configuration

### Create configuration file

```bash
dino init
```

This creates a `dino.yaml` file in your project root.

### Set your API key

```bash
# OpenAI
export OPENAI_API_KEY=sk-...

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Or use a local model with Ollama (no API key needed)
```

### Example `dino.yaml`

```yaml
# All packs enabled by default. Exclude what you don't need:
# exclude_packs:
#   - vue
#   - django

model: openai/gpt-4o-mini  # or anthropic/claude-3-5-sonnet, ollama/llama3
language: en
```

## Basic Usage

```bash
# Analyze current directory
dino check

# Analyze specific files
dino check src/views.py src/models.py

# Only analyze changed files (git diff)
dino check --diff

# Verbose output (show progress)
dino check -v

# Debug mode (detailed logs in dino.log)
dino check --debug

# Output as JSON
dino check --format json

# View LLM costs
dino logs cost
```

## Output Formats

| Format | Use Case |
|--------|----------|
| `text` | Colored terminal output (default) |
| `json` | Full JSON for tooling integration |
| `jsonl` | JSON Lines for streaming |

## GitHub Actions Integration

```yaml
name: Dinocheck
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5

      - run: uv add dinocheck
      - run: uv run dino check --diff
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```
