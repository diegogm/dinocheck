# Coding Agents

Dinocheck is **agent-native**: it integrates with AI coding assistants as a
"skill", and in the default agent mode the assistant itself performs the
analysis. No API keys, no model configuration - dinocheck selects the files
and rules, the agent reviews them, and dinocheck validates, scores, and
caches the results.

## How it works

```
dino brief --diff          ->  the agent analyzes      ->  dino report results.json
(files + rules + contract)     (using its own model)       (validate, score, cache, print)
```

1. **`dino brief`** runs the deterministic half: discovers files, matches the
   rules that trigger for each (with full checklists, fix guidance, and
   examples), resolves the cache, and emits a review brief.
2. **The agent** reads the brief, opens each file with its own tools, and
   evaluates only the listed rules.
3. **`dino report`** validates the agent's JSON against the output contract
   (with precise errors the agent can act on), converts it to issues,
   deduplicates, scores, caches, and prints the same formatted output as any
   other dinocheck run.

## Supported Agents

| Agent | Skill Location | Status |
|-------|---------------|--------|
| **Claude Code** | `.claude/skills/dinocheck/SKILL.md` | Fully supported |
| **OpenAI Codex** | `.codex/skills/dinocheck/SKILL.md` | Fully supported |
| **Gemini CLI** | `.gemini/skills/dinocheck/SKILL.md` | Fully supported |

## Quick Setup

### Option 1: Dedicated Command

```bash
# Create skill for detected agent(s)
dino skill

# Create skill for specific agent
dino skill --agent claude
dino skill --agent codex
dino skill --agent gemini

# Force overwrite existing skill
dino skill --force
```

### Option 2: During Init

```bash
dino init
```

If `.claude`, `.codex`, or `.gemini` folders exist, `dino init` will offer to create the corresponding skill.

## Claude Code Integration

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) is Anthropic's CLI for agentic coding with Claude.

### Setup

```bash
# If .claude folder exists
dino skill --agent claude

# Or create manually
mkdir -p .claude/skills/dinocheck
```

### Skill Features

The Claude Code skill includes:

- **Automatic triggering**: Claude uses dinocheck after writing code or when asked to review
- **Tool restrictions**: Only allows `dino` commands via `allowed-tools: Bash(dino:*)`
- **Agent-native workflow**: Claude generates the brief, performs the analysis itself, and submits the results with `dino report`

### Usage with Claude Code

```bash
# Claude will automatically run dinocheck when appropriate
claude "review the code I just wrote"
claude "check for issues before I commit"

# Or invoke the skill directly
claude "/dinocheck"
```

## OpenAI Codex Integration

[OpenAI Codex CLI](https://github.com/openai/codex) is OpenAI's agentic coding assistant.

### Setup

```bash
# If .codex folder exists
dino skill --agent codex
```

### Usage with Codex

```bash
codex "review the changes in src/"
codex "run dinocheck on this file"
```

## Gemini CLI Integration

[Gemini CLI](https://github.com/google/gemini-cli) is Google's command-line interface for Gemini.

### Setup

```bash
# If .gemini folder exists
dino skill --agent gemini
```

### Usage with Gemini CLI

```bash
gemini "check my code for issues"
gemini "review the authentication module"
```

## Skill Contents

All agent skills share the same workflow (templates ship with the package
under `dinocheck/skills/templates/`):

```markdown
---
name: dinocheck
description: >
  Run dinocheck code review: generate a review brief, analyze the code yourself
  following the brief's rules, then submit the results.
---

# Dinocheck - Agent-Native Code Review

## Workflow

1. dino brief --diff -o .dinocheck/brief.md
2. Read the brief; evaluate ONLY the listed rules per file (>= 80% confidence)
3. Write findings to .dinocheck/results.json (per the brief's output contract)
4. dino report .dinocheck/results.json
5. Fix validation errors and re-run dino report if needed
6. Present the output; do not fix code unless asked
```

## Best Practices

### 1. Use with `--diff` in CI-like workflows

When the agent is reviewing changes:

```bash
dino brief --diff
```

This only briefs files with uncommitted changes, making it faster and more focused.

### 2. Combine with other tools

Dinocheck complements traditional linters:

```bash
# Run fast linters first
ruff check .
mypy .

# Then run semantic analysis (agent workflow)
dino brief --diff
```

### 3. Review before commit

Configure your agent to run dinocheck before creating commits:

```
"Before committing, run the dinocheck skill and address any critical issues"
```

## Troubleshooting

### Skill not detected

Ensure the agent's configuration folder exists:

```bash
# For Claude Code
ls -la .claude/

# For Codex
ls -la .codex/

# For Gemini CLI
ls -la .gemini/
```

### Permission denied

Make sure the skill file is readable:

```bash
chmod 644 .claude/skills/dinocheck/SKILL.md
```

### Agent ignores skill

Some agents need to be restarted to detect new skills. Try:

```bash
# Restart your agent session
exit
claude  # or codex, gemini
```
