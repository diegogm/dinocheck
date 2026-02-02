# Configuration

Dinocheck can be configured via `dino.yaml` or environment variables.

## Configuration File

Create a `dino.yaml` in your project root:

```bash
dino init
```

### Full Example

```yaml
# LLM Model (provider/model format)
model: openai/gpt-4o-mini

# Response language (en, es, fr, de, etc.)
language: en

# Exclude packs you don't need (all enabled by default)
exclude_packs:
  - vue
  - docker

# Or explicitly enable only specific packs
# packs:
#   - python
#   - django

# Custom API endpoint (OpenAI-compatible)
# base_url: https://my-proxy.example.com/v1

# Maximum LLM calls per analysis (default: 10)
max_llm_calls: 10

# Analyze only specific directories (default: current directory)
# include_paths:
#   - src/
#   - lib/

# Exclude paths from analysis (glob patterns)
exclude_paths:
  - migrations
  - tests/fixtures

# Disable specific rules
disabled_rules:
  - python/broad-exception
```

## Path Filtering

### Include Paths

Specify default directories to analyze (when no paths are given via CLI):

```yaml
include_paths:
  - src/
  - lib/
```

When `include_paths` is set, `dino check` will only scan those directories by default.
CLI paths override this setting: `dino check other/` will ignore `include_paths`.

### Exclude Paths

Exclude files or directories from analysis using glob patterns:

```yaml
exclude_paths:
  - migrations
  - tests/fixtures
  - "*.generated.py"
```

Patterns are matched against directory names and file paths:
- `migrations` — excludes any directory named `migrations`
- `tests/fixtures` — excludes the `tests/fixtures` path
- `*.generated.py` — excludes files matching the pattern

These work alongside the built-in exclusions (hidden directories, `__pycache__`,
`node_modules`, `.venv`, `venv`).

## Environment Variables

### API Keys

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `AZURE_API_KEY` | Azure OpenAI API key |
| `GOOGLE_API_KEY` | Google AI API key |

### Config Overrides

You can override config values via environment variables with the `DINO_` prefix:

```bash
export DINO_MODEL=anthropic/claude-3-5-sonnet
export DINO_LANGUAGE=es
```

## Supported LLM Providers

| Provider | Model Examples |
|----------|----------------|
| **OpenAI** | `openai/gpt-4o`, `openai/gpt-4o-mini`, `openai/o1-preview` |
| **Anthropic** | `anthropic/claude-3-5-sonnet`, `anthropic/claude-3-opus` |
| **Ollama** | `ollama/llama3`, `ollama/codellama` |
| **Azure** | `azure/gpt-4o` |
| **Google** | `gemini/gemini-pro` |

See [LiteLLM docs](https://docs.litellm.ai/docs/providers) for 100+ supported providers.

## Configuration Priority

Settings are loaded in this order (highest priority first):

1. Environment variables (`DINO_MODEL`, `DINO_LANGUAGE`)
2. `.env` file (in same directory as `dino.yaml`)
3. `dino.yaml`
4. Default values
