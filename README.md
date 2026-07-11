<p align="center">
  <img src="https://raw.githubusercontent.com/diegogm/dinocheck/main/etc/dinocheck.png" alt="Dinocheck Logo" width="300">
</p>

<h1 align="center">Dinocheck</h1>

<p align="center">
  <strong>Your vibe coding companion - LLM-powered code critic</strong>
</p>

<p align="center">
  <a href="https://github.com/diegogm/dinocheck/actions/workflows/ci.yml"><img src="https://github.com/diegogm/dinocheck/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/diegogm/dinocheck"><img src="https://img.shields.io/codecov/c/github/diegogm/dinocheck" alt="Coverage"></a>
  <a href="https://pypi.org/project/dinocheck/"><img src="https://img.shields.io/pypi/v/dinocheck.svg" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11--3.13-blue.svg" alt="Python 3.11+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://diegogm.github.io/dinocheck/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue" alt="Documentation"></a>
</p>

---

Dinocheck is an AI-powered code critic designed to **enhance your vibe coding sessions**. It's not a traditional linter - those focus on syntax and style. Dinocheck uses AI to understand your code **semantically** and provide intelligent feedback on the things that matter: logic bugs, security issues, and architectural problems.

**Zero config by default**: when you code with an AI agent (Claude Code, Codex, Gemini CLI), the agent itself performs the review through the dinocheck skill - no API keys, no model setup. Dinocheck selects the files and rules, the agent analyzes, and dinocheck validates, scores, and caches the results.

```bash
$ dino report .dinocheck/results.json

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

## Quick Start

### Installation

```bash
pip install dinocheck
# or with uv
uv add dinocheck
```

### Agent mode (default - zero config)

If you code with Claude Code, Codex, or Gemini CLI, install the skill and
you're done. No API keys.

```bash
dino init    # creates dino.yaml and offers to create the agent skill
# or just:
dino skill   # creates the skill for detected agents
```

From then on, asking your agent to "review the code" (or the agent deciding
to check its own work) runs this loop:

```bash
dino brief --diff -o .dinocheck/brief.md   # 1. dinocheck picks files + rules
# 2. the agent analyzes each file following the brief's checklists
dino report .dinocheck/results.json        # 3. dinocheck validates, scores, caches
```

### API mode (CI / headless)

Where no agent is present, dinocheck can call an LLM API directly. Set
`mode: api` and a model in `dino.yaml`, export the API key, and use
`dino check`:

```yaml
mode: api
model: openai/gpt-5.2-codex  # or anthropic/claude-3-5-sonnet, ollama/llama3
language: en
```

```bash
export OPENAI_API_KEY=sk-...

dino check              # analyze current directory
dino check --diff       # only changed files
dino check -v           # verbose progress
dino check --format json
dino logs cost          # view LLM costs
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `dino brief [paths]` | Generate a review brief for the host agent (agent mode) |
| `dino brief --diff` | Brief covering only changed files |
| `dino report FILE` | Validate, score, and cache the agent's findings |
| `dino check [paths]` | Analyze code calling an LLM API (api mode) |
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
| `dino version` | Show version information |

## Rule Packs

| Pack | Description |
|------|-------------|
| **python** | Security, correctness, testing, and reliability rules for Python |
| **django** | ORM, transactions, DRF, migrations, and Celery task rules |
| **react** | Hooks, performance, security, patterns, and accessibility for JSX |
| **typescript** | Type safety, async patterns, and security for TS/JS |
| **css** | Performance, accessibility, maintainability, and compatibility for CSS |
| **docker** | Dockerfile security, build optimization, and runtime config |
| **docker-compose** | Compose security, networking, and reliability |
| **sh** | Shell script security, error handling, and portability |
| **vue** | Vue.js reactivity, templates, and XSS prevention |
| **latex** | Academic writing quality, citations, references, and math notation |

Use `dino packs info <pack>` to see all rules in a pack.

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

CI has no host agent, so `dino check` needs API mode (`DINO_MODE: api` or
`mode: api` in `dino.yaml`) and an API key.

## Supported LLM Providers

| Provider | Model Examples |
|----------|----------------|
| **OpenAI** | `gpt-4o`, `gpt-4o-mini`, `o1-preview` |
| **Anthropic** | `claude-3-5-sonnet`, `claude-3-opus` |
| **Ollama** | `ollama/llama3`, `ollama/codellama` |
| **Azure** | `azure/gpt-4o` |
| **Google** | `gemini/gemini-pro` |

See [LiteLLM docs](https://docs.litellm.ai/docs/providers) for 100+ supported providers.

## Documentation

Full documentation available at: **https://diegogm.github.io/dinocheck/**

### Build docs locally

```bash
fab docs
```

## Development

```bash
# Clone and install
git clone https://github.com/diegogm/dinocheck.git
cd dinocheck
uv sync --dev

# Run tests
fab test

# Run linters
fab lint

# Pre-deployment checks
fab predeploy
```

## License

MIT License - see [LICENSE](https://github.com/diegogm/dinocheck/blob/main/LICENSE) for details.

---

<p align="center">
  Made with care by the Dinocheck contributors
</p>
