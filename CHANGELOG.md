# Changelog

All notable changes to Dinocheck will be documented in this file.

## [0.1.0] - 2026-01-04

### Added
- Initial release of Dinocheck - LLM-powered code critic
- Python pack with 25 semantic rules
- Django pack with 22 rules for Django/DRF projects
- Text, JSON, and JSONL output formatters
- SQLite-based caching for analysis results
- LLM call logging and cost tracking
- Debug mode with detailed logging (`--debug`)
- Progress callbacks for verbose mode (`-v`)
- Colored terminal output using Rich

### Features
- **Rule packs**: Modular rule system with Python and Django packs
- **Multi-provider support**: OpenAI, Anthropic, Ollama via LiteLLM
- **Smart caching**: Content-addressed cache to avoid re-analyzing unchanged files
- **Git integration**: `--diff` flag to only analyze changed files
- **Cost tracking**: Track LLM usage and costs with `dino logs cost`

### Commands
- `dino check` - Analyze code with LLM-powered critique
- `dino packs list` - List available rule packs
- `dino packs info <pack>` - Show pack details and rules
- `dino explain <rule>` - Explain a specific rule
- `dino cache stats` - Show cache statistics
- `dino logs list` - View recent LLM calls
- `dino logs cost` - View cost summary
- `dino init` - Initialize configuration file

### Configuration
- YAML-based configuration (`dino.yaml`)
- Environment variable overrides (`DINO_MODEL`, `DINO_LANGUAGE`)
- Configurable packs, model, language, and budget
