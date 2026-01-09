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

Dinocheck is an AI-powered code critic designed to **enhance your vibe coding sessions**. It's not a traditional linter - those focus on syntax and style. Dinocheck uses GPT, Claude, or local models to understand your code **semantically** and provide intelligent feedback on the things that matter: logic bugs, security issues, and architectural problems.

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
| **LLM-First Analysis** | Uses GPT-4, Claude, or local models for semantic code review |
| **Rule Packs** | Python, Django, TypeScript, Docker, Compose, Shell, Vue |
| **Smart Caching** | SQLite cache avoids re-analyzing unchanged files |
| **Cost Tracking** | Monitor LLM usage and costs with `dino logs` |
| **Multi-Language** | Get feedback in English, Spanish, French, etc. |
| **100+ Providers** | OpenAI, Anthropic, Ollama, and more via LiteLLM |

## Quick Start

### Installation

```bash
pip install dinocheck
# or with uv
uv add dinocheck
```

### Configuration

```bash
# Create dino.yaml
dino init

# Set your API key
export OPENAI_API_KEY=sk-...
```

Example `dino.yaml`:

```yaml
# All packs enabled by default. Exclude what you don't need:
# exclude_packs:
#   - vue
#   - django

model: openai/gpt-4o-mini  # or anthropic/claude-3-5-sonnet, ollama/llama3
language: en
```

### Usage

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

## CLI Reference

| Command | Description |
|---------|-------------|
| `dino check [paths]` | Analyze code with LLM |
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
| **typescript** | Type safety, async patterns, and security for TS/JS |
| **docker** | Dockerfile security, build optimization, and runtime config |
| **docker-compose** | Compose security, networking, and reliability |
| **sh** | Shell script security, error handling, and portability |
| **vue** | Vue.js reactivity, templates, and XSS prevention |

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
```

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
