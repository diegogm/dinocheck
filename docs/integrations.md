# Coding Agents

Dinocheck integrates with popular AI coding assistants as a "skill" - allowing the agent to automatically run code reviews when appropriate.

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
- **Workflow guidance**: Instructs Claude on how to interpret and act on findings

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

All agent skills share similar content:

```markdown
---
name: dinocheck
description: >
  Run LLM-powered code review with dinocheck. Use when you finish writing code,
  before committing, or when the user asks to review, check, or analyze code quality.
---

# Dinocheck - LLM Code Review

## When to use

- After writing or modifying code
- Before committing changes
- When asked to review code quality
- When looking for potential bugs or improvements

## Commands

# Check current directory
dino check

# Check only changed files
dino check --diff

# Verbose output
dino check -v

## Workflow

1. Run `dino check` on the relevant code
2. Review the issues found
3. Address critical and major issues first
4. Use `dino explain <rule-id>` for more details
```

## Best Practices

### 1. Use with `--diff` in CI-like workflows

When the agent is reviewing changes:

```bash
dino check --diff
```

This only analyzes files with uncommitted changes, making it faster and more focused.

### 2. Combine with other tools

Dinocheck complements traditional linters:

```bash
# Run fast linters first
ruff check .
mypy .

# Then run semantic analysis
dino check --diff
```

### 3. Review before commit

Configure your agent to run dinocheck before creating commits:

```
"Before committing, run dino check --diff and address any critical issues"
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
