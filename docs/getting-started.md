# Getting Started

## Installation

```bash
pip install dinocheck
# or with uv
uv add dinocheck
```

## How it works

Dinocheck is agent-native: your AI coding agent (Claude Code, Codex, Gemini
CLI) performs the review itself. Zero config - no API keys, no model setup,
no external LLM calls.

## Setup

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

## Output Formats

| Format | Use Case |
|--------|----------|
| `text` | Colored terminal output (default) |
| `json` | Full JSON for tooling integration |
| `jsonl` | JSON Lines for streaming |

## CI Integration

Dinocheck needs an AI coding agent to perform the analysis, so in CI you run
it through an agent CLI (e.g. Claude Code in headless mode):

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
      - run: uv run dino skill --agent claude
      - run: |
          claude -p "Run the dinocheck skill on the files changed in this PR \
            and summarize the findings. Fail only on blocker or critical issues."
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```
