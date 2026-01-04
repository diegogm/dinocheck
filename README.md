<p align="center">
  <img src="dinocheck.png" alt="Dinocheck Logo" width="300">
</p>

<h1 align="center">Dinocheck</h1>

<p align="center">
  <strong>Your vibe coding companion - LLM-powered code critic</strong>
</p>

<p align="center">
  <a href="https://github.com/diegogm/dinocheck/actions/workflows/ci.yml"><img src="https://github.com/diegogm/dinocheck/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/diegogm/dinocheck"><img src="https://codecov.io/gh/diegogm/dinocheck/branch/main/graph/badge.svg" alt="Coverage"></a>
  <a href="https://pypi.org/project/dinocheck/"><img src="https://img.shields.io/pypi/v/dinocheck.svg" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11--3.13-blue.svg" alt="Python 3.11+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

---

Dinocheck is an AI-powered code linter designed for **vibe coding**. It doesn't do pattern matching - that's what traditional linters are for. Instead, it uses GPT, Claude, or local models to understand your code **semantically** and provide intelligent feedback.

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
| **Rule Packs** | Python and Django packs with 40+ rules |
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

Create `dino.yaml` in your project:

```yaml
dinocheck:
  packs:
    - python
    - django

  provider:
    model: gpt-4o-mini
    api_key_env: OPENAI_API_KEY

  output:
    language: en
```

Or use environment variables:

```bash
export OPENAI_API_KEY=sk-...
export DINO_MODEL=gpt-4o-mini
```

### Usage

```bash
# Analyze current directory
dino check

# Analyze specific files
dino check src/views.py src/models.py

# Only analyze changed files (git diff)
dino check --diff

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
| `dino packs list` | List available packs |
| `dino packs info NAME` | Show pack details |
| `dino explain RULE_ID` | Explain a rule |
| `dino cache stats` | Show cache statistics |
| `dino cache clear` | Clear the cache |
| `dino logs list` | View LLM call history |
| `dino logs cost` | View cost summary |
| `dino init` | Create dino.yaml |

## Rule Packs

### Python Pack

| Rule | Description |
|------|-------------|
| `python/sql-injection` | SQL injection vulnerabilities |
| `python/insecure-deserialization` | Unsafe pickle/yaml loading |
| `python/concurrency-safety` | Race conditions and deadlocks |
| `python/error-handling` | Missing or incorrect error handling |
| `python/resource-lifecycle` | Unclosed files, connections |
| `python/api-contract-break` | Breaking API changes |

### Django Pack

| Category | Rules |
|----------|-------|
| **ORM** | N+1 queries, missing select_related, queryset performance |
| **Security** | Missing permissions, field whitelisting, ownership filters |
| **Transactions** | Atomic scope, select_for_update, on_commit side effects |
| **DRF** | Permission classes, throttling, async blocking calls |
| **Migrations** | Data loss, large indexes, NOT NULL two-phase |
| **Testing** | Missing auth tests, business logic coverage |

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
      - run: uv run dino check --diff --format sarif -o results.sarif
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

## Configuration Reference

```yaml
dinocheck:
  version: "1.0"

  packs:
    - python
    - django

  provider:
    model: gpt-4o-mini          # gpt-4o, claude-3-5-sonnet, ollama/llama3
    api_key_env: OPENAI_API_KEY

  output:
    default_format: text
    language: en                # en, es, fr, de, pt, etc.

  budget:
    max_llm_calls_local: 1      # Max calls per file (local)
    max_llm_calls_pr: 3         # Max calls per file (PR mode)

  cache:
    enabled: true
    database: .dinocheck_cache/cache.db
    ttl_hours: 168              # 7 days

  packs_config:
    django:
      check_drf: auto           # auto, always, never
      disabled_rules:
        - django/structured-logging
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

## Development

```bash
# Clone and install
git clone https://github.com/your-org/dinocheck.git
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

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with care by the Dinocheck contributors
</p>
