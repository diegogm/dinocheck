"""Dinocheck CLI entry point.

Dinocheck is a vibe coding companion - an LLM-powered code critic that helps
you catch issues while you code. It's designed to run alongside your development
workflow, not to fix code for you.
"""

from pathlib import Path
from typing import Annotated

import click
import typer

from dinocheck import __version__
from dinocheck.cli.console import console
from dinocheck.core.config import ConfigManager

# Create main app
app = typer.Typer(
    name="dino",
    help="Dinocheck: Your vibe coding companion - LLM-powered code critic",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
)


# Global options
ConfigOption = Annotated[
    Path | None,
    typer.Option(
        "-c",
        "--config",
        help="Path to dino.yaml config file",
        exists=True,
        readable=True,
    ),
]

VerboseOption = Annotated[
    int,
    typer.Option(
        "-v",
        "--verbose",
        count=True,
        help="Increase verbosity (-v, -vv, -vvv)",
    ),
]

QuietOption = Annotated[
    bool,
    typer.Option(
        "-q",
        "--quiet",
        help="Suppress non-essential output",
    ),
]


@app.command()
def check(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(
            help="Files/directories to analyze (default: current directory)",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format",
            click_type=click.Choice(["text", "json", "jsonl"]),
        ),
    ] = "text",
    pack: Annotated[
        str | None,
        typer.Option(
            "--pack",
            help="Run only specific pack(s), comma-separated",
        ),
    ] = None,
    rule: Annotated[
        str | None,
        typer.Option(
            "--rule",
            help="Run only specific rule(s), comma-separated",
        ),
    ] = None,
    budget: Annotated[
        int | None,
        typer.Option(
            "--budget",
            help="Override max LLM calls",
        ),
    ] = None,
    diff: Annotated[
        bool,
        typer.Option(
            "--diff",
            help="Only analyze files with local git changes",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Write output to file",
        ),
    ] = None,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Write detailed debug log to dino.log",
        ),
    ] = False,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="Disable cache, re-analyze all files",
        ),
    ] = False,
    config: ConfigOption = None,
    verbose: VerboseOption = 0,
    quiet: QuietOption = False,
) -> None:
    """Analyze code with LLM-powered critique.

    Dinocheck sends your code to an LLM for intelligent review. It doesn't do
    pattern matching - that's what other linters are for. Instead, it uses
    GPT/Claude/local models to understand your code semantically.

    Examples:
        dino check                    # Check current directory
        dino check src/               # Check specific directory
        dino check views.py models.py # Check specific files
        dino check --diff             # Only files with local changes
        dino check --format json      # Output as JSON
        dino check --pack django      # Use only Django rules
    """
    from dinocheck.core.engine import Engine
    from dinocheck.core.logging import setup_logger

    # Setup debug logging if requested
    if debug:
        setup_logger(debug=True)
        console.info("Debug mode enabled - writing to dino.log", err=True)

    # Load and validate config
    config_manager = ConfigManager(config)
    cfg = config_manager.load()
    errors = config_manager.validate()
    if errors:
        for error in errors:
            console.error(f"Config error: {error}")
        raise typer.Exit(2)

    # Override budget if specified
    if budget is not None:
        cfg.max_llm_calls = budget

    # Filter packs if specified
    if pack:
        cfg.packs = [p.strip() for p in pack.split(",")]

    # Run analysis
    engine = Engine(cfg)

    if not quiet:
        console.info(f"Dinocheck v{__version__} - Analyzing...", err=True)

    # Create progress callback for verbose mode
    def on_progress(step: str, details: str) -> None:
        if verbose >= 1:
            # Handle file-specific progress with nicer formatting
            if step == "file_skip":
                # Parse: "path → 0 rules, skipped"
                path = details.split(" → ")[0]
                console.file_status(path, 0, "skip", err=True)
            elif step == "file_cache":
                # Parse: "path → N rules, cached"
                parts = details.split(" → ")
                path = parts[0]
                rules = int(parts[1].split(" ")[0])
                console.file_status(path, rules, "cache", err=True)
            elif step == "file_analyze":
                # Parse: "path → N rules, will analyze"
                parts = details.split(" → ")
                path = parts[0]
                rules = int(parts[1].split(" ")[0])
                console.file_status(path, rules, "analyze", err=True)
            else:
                console.step(step, details, err=True)

    try:
        result = engine.analyze(
            paths=paths or [Path(".")],
            rule_filter=rule.split(",") if rule else None,
            on_progress=on_progress if verbose else None,
            diff_only=diff,
            no_cache=no_cache,
        )
    except Exception as e:
        console.error(f"Analysis error: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(2) from None

    # Format output
    from dinocheck.cli.formatters import get_formatter

    formatter = get_formatter(format)
    formatted = formatter.format(result)

    # Write output
    if output:
        output.write_text(formatted)
        if not quiet:
            console.success(f"Output written to {output}")
    else:
        console.print(formatted)


# Packs subcommand
packs_app = typer.Typer(help="Manage rule packs")
app.add_typer(packs_app, name="packs")


@packs_app.command("list")
def packs_list(
    config: ConfigOption = None,
) -> None:
    """List available and installed packs."""
    from dinocheck.packs.loader import get_all_packs

    cfg = ConfigManager(config).load()

    table = console.table(
        title="Available Packs",
        columns=[
            ("Pack", "cyan"),
            ("Version", ""),
            ("Status", ""),
            ("Rules", ""),
        ],
    )

    for pack in get_all_packs():
        status = "enabled" if pack.name in cfg.packs else "disabled"
        status_style = "green" if status == "enabled" else "dim"
        table.add_row(
            pack.name,
            pack.version,
            f"[{status_style}]{status}[/{status_style}]",
            str(len(pack.rules)),
        )

    console.print_table(table)


@packs_app.command("info")
def packs_info(
    pack: Annotated[str, typer.Argument(help="Pack name")],
) -> None:
    """Show pack details and rules."""
    from dinocheck.packs.loader import get_pack

    try:
        pack_obj = get_pack(pack)

        console.header(f"{pack_obj.name} v{pack_obj.version}")
        console.print(f"{len(pack_obj.rules)} rules", style="dim")
        console.print()

        table = console.table(
            columns=[
                ("ID", "cyan"),
                ("Name", ""),
                ("Level", ""),
            ],
        )

        level_colors = {
            "blocker": "bright_red",
            "critical": "red",
            "major": "yellow",
            "minor": "cyan",
            "info": "blue",
        }

        for rule in pack_obj.rules:
            level = rule.level.value
            color = level_colors.get(level, "")
            table.add_row(
                rule.id,
                rule.name,
                f"[{color}]{level}[/{color}]",
            )

        console.print_table(table)

    except Exception as e:
        console.error(str(e))
        raise typer.Exit(2) from None


# Cache subcommand
cache_app = typer.Typer(help="Manage analysis cache")
app.add_typer(cache_app, name="cache")


@cache_app.command("stats")
def cache_stats() -> None:
    """Show cache statistics."""
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import DEFAULT_CACHE_DB

    cache = SQLiteCache(Path(DEFAULT_CACHE_DB), ttl_hours=168)
    stats = cache.stats()

    console.header("Cache Statistics")
    console.status_line("Entries", str(stats.entries))
    console.status_line("Size", f"{stats.size_bytes / 1024:.1f} KB")


@cache_app.command("clear")
def cache_clear(
    older: Annotated[
        int | None,
        typer.Option(
            "--older",
            help="Clear entries older than N days",
        ),
    ] = None,
) -> None:
    """Clear all cached results."""
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import DEFAULT_CACHE_DB

    cache = SQLiteCache(Path(DEFAULT_CACHE_DB), ttl_hours=168)

    hours = older * 24 if older else None
    deleted = cache.clear(hours)

    console.success(f"Cleared {deleted} cache entries")


# Logs subcommand
logs_app = typer.Typer(help="View LLM call history")
app.add_typer(logs_app, name="logs")


@logs_app.command("list")
def logs_list(
    limit: Annotated[
        int,
        typer.Option(
            "-n",
            "--limit",
            help="Number of entries to show",
        ),
    ] = 20,
) -> None:
    """List recent LLM calls."""
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import DEFAULT_CACHE_DB

    cache = SQLiteCache(Path(DEFAULT_CACHE_DB), ttl_hours=168)
    logs = cache.get_llm_logs(limit)

    if not logs:
        console.info("No LLM calls logged yet")
        return

    table = console.table(
        title="Recent LLM Calls",
        columns=[
            ("ID", "dim"),
            ("Timestamp", ""),
            ("Model", "cyan"),
            ("Pack", ""),
            ("Files", ""),
            ("Tokens", ""),
            ("Cost", "green"),
            ("Issues", "yellow"),
        ],
    )

    for log in logs:
        table.add_row(
            log.id[:8],
            log.timestamp[:19],
            log.model,
            log.pack,
            str(len(log.files)),
            str(log.total_tokens),
            f"${log.cost_usd:.4f}",
            str(log.issues_found),
        )

    console.print_table(table)


@logs_app.command("show")
def logs_show(
    log_id: Annotated[str, typer.Argument(help="Log ID (partial match)")],
) -> None:
    """Show details of a specific LLM call."""
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import DEFAULT_CACHE_DB

    cache = SQLiteCache(Path(DEFAULT_CACHE_DB), ttl_hours=168)
    log = cache.get_llm_log(log_id)

    if not log:
        console.error(f"Log not found: {log_id}")
        raise typer.Exit(2)

    console.header(f"LLM Call {log.id[:12]}...")

    console.status_line("Timestamp", log.timestamp)
    console.status_line("Model", log.model, style="cyan")
    console.status_line("Pack", log.pack)
    console.status_line("Duration", f"{log.duration_ms}ms")

    console.print()
    console.status_line(
        "Tokens",
        f"{log.prompt_tokens} prompt + {log.completion_tokens} completion = {log.total_tokens}",
    )
    console.status_line("Cost", f"${log.cost_usd:.4f}", style="green")
    console.status_line("Issues found", str(log.issues_found), style="yellow")

    console.print()
    console.print("Files analyzed:", style="bold")
    for f in log.files:
        console.print(f"  - {f}", style="dim")


@logs_app.command("cost")
def logs_cost(
    days: Annotated[
        int,
        typer.Option(
            "-d",
            "--days",
            help="Number of days to summarize",
        ),
    ] = 30,
) -> None:
    """Show cost summary."""
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import DEFAULT_CACHE_DB

    cache = SQLiteCache(Path(DEFAULT_CACHE_DB), ttl_hours=168)
    summary = cache.get_cost_summary(days)

    console.header(f"Cost Summary (Last {days} Days)")

    console.status_line("Total Calls", str(summary.total_calls))
    console.status_line("Total Tokens", f"{summary.total_tokens:,}")
    console.status_line("Total Cost", f"${summary.total_cost:.4f}", style="green")
    console.status_line("Avg Cost/Call", f"${summary.avg_cost_per_call:.4f}", style="dim")
    console.status_line("Issues Found", str(summary.total_issues), style="yellow")


@app.command()
def explain(
    issue_id: Annotated[str, typer.Argument(help="Issue ID or rule ID")],
    examples: Annotated[
        bool,
        typer.Option(
            "--examples",
            help="Include code examples",
        ),
    ] = False,
) -> None:
    """Explain a specific rule.

    Examples:
        dino explain django/n-plus-one
        dino explain n-plus-one --examples
    """
    from dinocheck.packs.loader import get_all_packs

    level_colors = {
        "blocker": "bright_red",
        "critical": "red",
        "major": "yellow",
        "minor": "cyan",
        "info": "blue",
    }

    # Find rule across all packs
    for pack in get_all_packs():
        for rule in pack.rules:
            if rule.id == issue_id or rule.id.endswith(f"/{issue_id}"):
                console.header(f"{rule.name}")
                console.print(f"ID: {rule.id}", style="dim")

                level = rule.level.value
                color = level_colors.get(level, "")
                console.print(f"Level: [{color}]{level}[/{color}]")
                console.print(f"Category: {rule.category}", style="dim")

                console.print()
                console.print("Description:", style="bold")
                console.print(rule.description)

                console.print()
                console.print("Checklist:", style="bold")
                for item in rule.checklist:
                    console.print(f"  - {item}", style="dim")

                console.print()
                console.print("How to fix:", style="bold green")
                console.print(rule.fix)

                if examples and rule.examples:
                    console.print()
                    console.print("Examples:", style="bold")
                    if "bad" in rule.examples:
                        console.print("Bad:", style="red")
                        console.print(rule.examples["bad"], style="dim")
                    if "good" in rule.examples:
                        console.print("Good:", style="green")
                        console.print(rule.examples["good"], style="dim")

                return

    console.error(f"Rule not found: {issue_id}")
    raise typer.Exit(2)


@app.command()
def init(
    path: Annotated[
        Path,
        typer.Argument(help="Directory to initialize"),
    ] = Path("."),
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing config",
        ),
    ] = False,
) -> None:
    """Initialize dino.yaml configuration file.

    Creates a starter configuration for Dinocheck with sensible defaults.
    Also offers to create a Claude Code skill if .claude folder exists.
    """
    config_path = path / "dino.yaml"

    if config_path.exists() and not force:
        console.error(f"Config already exists: {config_path}")
        console.print("Use --force to overwrite", style="dim")
        raise typer.Exit(1)

    default_config = """\
# Dinocheck - Your vibe coding companion
# https://github.com/diegogm/dinocheck

# Rule packs to enable
packs:
  - python
  # - django  # Uncomment for Django projects

# LLM configuration
model: openai/gpt-4o-mini  # Or: anthropic/claude-3-5-sonnet, ollama/llama3
language: en

# Analysis budget (max LLM calls per run)
max_llm_calls: 10

# Disable specific rules (by ID)
# disabled_rules:
#   - python/some-rule-id
"""

    config_path.write_text(default_config)
    console.success(f"Created config: {config_path}")

    # Check if .claude folder exists and offer to create skill
    claude_dir = path / ".claude"
    if claude_dir.is_dir():
        _offer_claude_skill(path, claude_dir, force)


def _offer_claude_skill(path: Path, claude_dir: Path, force: bool) -> None:
    """Offer to create a Claude Code skill for dinocheck."""
    skill_dir = claude_dir / "skills" / "dinocheck"
    skill_file = skill_dir / "SKILL.md"

    if skill_file.exists() and not force:
        console.info("Claude Code skill already exists", err=True)
        return

    # Ask user if they want to create the skill
    create_skill = typer.confirm(
        "\nDetected .claude folder. Create a Claude Code skill for dinocheck?",
        default=True,
    )

    if not create_skill:
        return

    skill_content = """\
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
dino check

# Check specific files or directories
dino check src/

# Check only changed files (git diff)
dino check --diff

# Verbose output with progress
dino check -v
```

## Workflow

1. Run `dino check` on the relevant code
2. Review the issues found
3. Address critical and major issues first
4. Use `dino explain <rule-id>` for more details on any rule
"""

    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(skill_content)
    console.success(f"Created Claude Code skill: {skill_file}")


@app.command()
def version() -> None:
    """Show Dinocheck version information."""
    console.print(f"Dinocheck v{__version__}", style="bold cyan")
    console.print("Your vibe coding companion", style="dim")


if __name__ == "__main__":
    app()
