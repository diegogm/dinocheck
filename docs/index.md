<p align="center">
  <img src="https://raw.githubusercontent.com/diegogm/dinocheck/main/etc/dinocheck.png" alt="Dinocheck Logo" width="300">
</p>

# Dinocheck

**Your vibe coding companion - LLM-powered code critic**

Dinocheck is an AI-powered code critic designed to **enhance your vibe coding sessions**. It's not a traditional linter - those focus on syntax and style. Dinocheck uses AI to understand your code **semantically** and provide intelligent feedback on the things that matter: logic bugs, security issues, and architectural problems.

**Zero config by default**: when you code with an AI agent (Claude Code, Codex, Gemini CLI), the agent itself performs the review through the dinocheck skill - no API keys, no model setup. See [Coding Agents](integrations.md).

```bash
$ dino check src/views.py

------------------------------------------------------------
✓ Analysis Complete - Score: 72/100
------------------------------------------------------------

Issues (2):

------------------------------------------------------------
 src/views.py
------------------------------------------------------------

  [MAJOR] N+1 query detected in order iteration
     Rule: django/n-plus-one

     Why: Iterating over `Order.objects.filter(user=user)` and accessing
     `order.items.all()` inside the loop causes one query per order.

     Actions:
       • Use `prefetch_related('items')` to fetch all items in a single query.

  ----------------------------------------

  [CRITICAL] Missing permission check in delete_account view
     Rule: django/api-authorization

     Why: The `delete_account` view modifies user data but has no permission
     check. Any authenticated user could delete any account by guessing the ID.

     Actions:
       • Add ownership validation: `if account.user != request.user: return 403`
       • Consider using DRF's permission classes for consistent access control.

Checked 12 files (10 cached) in 1842ms for $0.003
```

## Why Dinocheck?

Traditional linters catch syntax errors and style issues. Dinocheck catches **logic bugs, security issues, and architectural problems** that only an AI can understand:

- Detects N+1 queries that would kill your database
- Spots missing authorization checks before they become CVEs
- Finds race conditions in your async code
- Identifies test mocks that hide real bugs

## Philosophy

Dinocheck is a **linter, not a fixer**. It's designed to be your coding companion:

- Reviews your code with LLM intelligence
- Points out issues and explains **why** they matter
- Lets **you** decide how to fix them

This fits the vibe coding workflow: you write code with AI assistance, and Dinocheck provides a second opinion.

## Features

| Feature | Description |
|---------|-------------|
| **Agent-Native** | Your AI coding agent performs the review - zero config, no API keys |
| **LLM-First Analysis** | Semantic code review driven by AI, not pattern matching |
| **Rule Packs** | Python, Django, React, TypeScript, CSS, Docker, Compose, Shell, Vue, LaTeX |
| **Smart Caching** | SQLite cache avoids re-analyzing unchanged files (per analyzer) |
| **API Mode for CI** | Optional headless mode via OpenAI, Anthropic, Ollama, and 100+ providers (LiteLLM) |
| **Multi-Language** | Get feedback in English, Spanish, French, etc. |
| **Cost Tracking** | Monitor LLM usage and costs with `dino logs` |
