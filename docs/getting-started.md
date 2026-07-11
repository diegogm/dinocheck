# Getting Started

## Installation

```bash
pip install dinocheck
# or with uv
uv add dinocheck
```

## Choose your mode

Dinocheck has two analysis modes:

- **Agent mode (default)**: your AI coding agent (Claude Code, Codex, Gemini
  CLI) performs the review itself. Zero config - no API keys, no model setup.
- **API mode**: `dino check` calls an LLM API directly. For CI and headless
  environments.

## Agent mode (default)

### Setup

```bash
dino init    # creates dino.yaml and offers to create the agent skill
# or just:
dino skill   # creates the skill for detected agents (.claude/.codex/.gemini)
```

That's it. When you ask your agent to review code (or it decides to check its
own work), the skill runs this loop:

```bash
# 1. Dinocheck selects the files and the rules that apply to each
dino brief --diff -o .dinocheck/brief.md

# 2. The agent reads the brief and analyzes each file with its checklists

# 3. Dinocheck validates the findings, scores, caches, and prints the result
dino report .dinocheck/results.json
```

You can also run `dino brief` yourself and paste the brief into any assistant.

## API mode (CI / headless)

### Configure

```yaml
# dino.yaml
mode: api
model: openai/gpt-5.2-codex  # or anthropic/claude-3-5-sonnet, ollama/llama3
language: en
```

```bash
# OpenAI
export OPENAI_API_KEY=sk-...

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Or use a local model with Ollama (no API key needed)
```

### Basic Usage

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
          DINO_MODE: api
```

CI has no host agent, so `dino check` needs API mode and an API key.
