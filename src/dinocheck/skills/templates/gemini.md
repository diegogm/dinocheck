---
name: dinocheck
description: >
  Run dinocheck code review: generate a review brief, analyze the code yourself
  following the brief's rules, then submit the results. Use when you finish
  writing code, before committing, or when asked to review, check, or analyze
  code quality. No API keys or LLM configuration needed.
---

# Dinocheck - Agent-Native Code Review

Dinocheck selects the files and the rules; YOU perform the analysis. It then
validates, scores, and caches your findings.

## When to use

- After writing or modifying code
- Before committing changes
- When asked to review code quality
- When looking for potential bugs or improvements

## Workflow

1. Generate the review brief:

   ```bash
   dino brief --diff -o .dinocheck/brief.md   # changed files only (preferred)
   dino brief src/ -o .dinocheck/brief.md     # or specific paths
   ```

2. Read `.dinocheck/brief.md`. If it says there is nothing to analyze, tell
   the user everything is up to date and stop.

3. For each file listed in the brief:
   - Open the file and evaluate ONLY the rules listed for it, using their
     checklists. Do not invent rules.
   - Only report issues you are at least 80% confident about.

4. Write your findings to `.dinocheck/results.json` following the brief's
   output contract exactly (one entry per listed file, empty `issues` array
   when a file is clean).

5. Submit and show the formatted result:

   ```bash
   dino report .dinocheck/results.json
   ```

6. If `dino report` prints validation errors, fix `results.json` and re-run it.

7. Present the output to the user, most severe issues first. Dinocheck is a
   linter, not a fixer - do not modify code unless the user asks.

Use `dino explain <rule-id>` for more details on any rule.
