---
name: dinocheck
description: >
  Run LLM-powered code review with dinocheck. Use when you finish writing code,
  before committing, or when the user asks to review, check, or analyze code quality.
allowed-tools: Bash(dino:*)
---

# Dinocheck - LLM Code Review

Run dinocheck to get AI-powered code review feedback.

## When to use

- After writing or modifying code
- Before committing changes
- When asked to review code quality
- When looking for potential bugs or improvements

## Commands

```bash
# Check current directory
fab dino check
```

## Workflow

1. Run `fab dino check` on the relevant code
2. Review the issues found
3. Address critical and major issues first
4. Use `fab dino -a "explain <rule-id>"` for more details on any rule
