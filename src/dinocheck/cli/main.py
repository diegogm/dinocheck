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

    if cfg.mode == "agent":
        console.error("'dino check' calls an external LLM API, but mode is 'agent' (the default).")
        console.print("In agent mode your AI coding agent runs the review:", err=True)
        console.print("  1. dino brief --diff -o .dinocheck/brief.md", style="dim", err=True)
        console.print(
            "  2. (the agent analyzes the brief and writes .dinocheck/results.json)",
            style="dim",
            err=True,
        )
        console.print("  3. dino report .dinocheck/results.json", style="dim", err=True)
        console.print(
            "To call an API directly instead, set 'mode: api' and a model in dino.yaml.",
            style="dim",
            err=True,
        )
        raise typer.Exit(2)

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
        cfg.packs = [p.strip() for p in pack.split(",") if p.strip()]

    # Run analysis
    engine = Engine(cfg, debug=debug)

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
            rule_filter=[r.strip() for r in rule.split(",") if r.strip()] if rule else None,
            on_progress=on_progress if verbose and not quiet else None,
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
        # Print directly - formatted already contains ANSI codes from Rich
        print(formatted, end="")


@app.command()
def brief(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(
            help="Files/directories to analyze (default: current directory)",
        ),
    ] = None,
    diff: Annotated[
        bool,
        typer.Option(
            "--diff",
            help="Only analyze files with local git changes",
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Brief format",
            click_type=click.Choice(["markdown", "json"]),
        ),
    ] = "markdown",
    embed_code: Annotated[
        bool,
        typer.Option(
            "--embed-code",
            help="Embed file contents in the brief (for agents without file access)",
        ),
    ] = False,
    pack: Annotated[
        str | None,
        typer.Option(
            "--pack",
            help="Use only specific pack(s), comma-separated",
        ),
    ] = None,
    rule: Annotated[
        str | None,
        typer.Option(
            "--rule",
            help="Use only specific rule(s), comma-separated",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Write brief to file",
        ),
    ] = None,
    config: ConfigOption = None,
    quiet: QuietOption = False,
) -> None:
    """Generate a review brief for the host coding agent (agent mode, step 1).

    Selects the files to review and the rules that apply to each, and emits
    the instructions the agent needs to perform the analysis itself. No LLM
    API is called and no API key is needed. Submit the agent's findings
    afterwards with 'dino report'.

    Examples:
        dino brief --diff -o .dinocheck/brief.md  # Changed files only
        dino brief src/                           # Specific directory
        dino brief --format json                  # Machine-readable brief
    """
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import AGENT_ANALYZER, DEFAULT_CACHE_DB
    from dinocheck.core.planner import AnalysisPlanner
    from dinocheck.llm.prompts import BriefBuilder

    cfg = ConfigManager(config).load()

    if pack:
        cfg.packs = [p.strip() for p in pack.split(",") if p.strip()]
    rule_filter = [r.strip() for r in rule.split(",") if r.strip()] if rule else None

    cache_path = Path(DEFAULT_CACHE_DB)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = SQLiteCache(cache_path, ttl_hours=168)

    planner = AnalysisPlanner(cfg, cache, analyzer=AGENT_ANALYZER)
    plan = planner.plan(paths or [Path(".")], rule_filter=rule_filter, diff_only=diff)

    if format == "json":
        formatted = BriefBuilder.build_json(plan, cfg, embed_code=embed_code)
    else:
        formatted = BriefBuilder.build_markdown(plan, cfg, embed_code=embed_code)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(formatted, encoding="utf-8")
        if not quiet:
            console.success(f"Brief written to {output}", err=True)
    else:
        print(formatted, end="")

    if not quiet:
        console.info(
            f"{len(plan.tasks)} file(s) to review, {plan.cache_hits} cached, "
            f"{plan.skipped_no_rules} skipped (no rules)",
            err=True,
        )


@app.command()
def report(
    results: Annotated[
        Path,
        typer.Argument(
            help="Agent results JSON file matching the brief's output contract",
        ),
    ],
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format",
            click_type=click.Choice(["text", "json", "jsonl"]),
        ),
    ] = "text",
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Write output to file",
        ),
    ] = None,
    config: ConfigOption = None,
    quiet: QuietOption = False,
) -> None:
    """Validate and score the host agent's findings (agent mode, step 2).

    Reads the results JSON the agent produced from a 'dino brief', validates
    it against the output contract, converts it to issues, deduplicates,
    scores, caches, and prints the formatted result. Validation problems are
    reported precisely so the agent can fix the file and retry.

    Examples:
        dino report .dinocheck/results.json
        dino report results.json --format json
    """
    import sys
    import time as time_module

    from pydantic import ValidationError

    from dinocheck.cli.formatters import get_formatter
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import AGENT_ANALYZER, DEFAULT_CACHE_DB
    from dinocheck.core.issue_factory import IssueFactory
    from dinocheck.core.planner import AnalysisPlanner
    from dinocheck.core.scoring import ScoreCalculator
    from dinocheck.core.types import AnalysisResult, Issue
    from dinocheck.llm.schemas import AgentReport, CriticResponse

    start_time = time_module.time()
    cfg = ConfigManager(config).load()

    if str(results) == "-":
        raw = sys.stdin.read()
    else:
        if not results.exists():
            console.error(f"Results file not found: {results}")
            raise typer.Exit(2)
        raw = results.read_text(encoding="utf-8")

    try:
        agent_report = AgentReport.model_validate_json(raw)
    except ValidationError as e:
        console.error("Results file does not match the output contract:")
        for err in e.errors():
            location = ".".join(str(part) for part in err["loc"]) or "<root>"
            console.print(f"  {location}: {err['msg']}", err=True)
        console.print("Fix the JSON and run 'dino report' again.", style="dim", err=True)
        raise typer.Exit(2) from None

    if not agent_report.files:
        console.error("Report contains no files. Include one entry per file listed in the brief.")
        raise typer.Exit(2)

    cache_path = Path(DEFAULT_CACHE_DB)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = SQLiteCache(cache_path, ttl_hours=168)

    # Re-plan over the reported paths to recompute triggered rules and
    # cache keys from the files' CURRENT content
    planner = AnalysisPlanner(cfg, cache, analyzer=AGENT_ANALYZER)
    report_paths = [Path(f.path) for f in agent_report.files]
    plan = planner.plan(report_paths, no_cache=True)
    tasks_by_path = {str(task.file_ctx.path): task for task in plan.tasks}

    factory = IssueFactory()
    warnings: list[str] = []
    all_issues: list[Issue] = []
    files_processed = 0

    for file_report in agent_report.files:
        task = tasks_by_path.get(file_report.path)
        if task is None:
            warnings.append(
                f"{file_report.path}: file not found or no applicable rules - entry ignored"
            )
            continue

        response = CriticResponse(issues=file_report.issues)
        issues, issue_warnings = factory.create_issues(
            response, task.file_ctx, plan.pack_name, source="agent"
        )
        warnings.extend(issue_warnings)
        all_issues.extend(issues)
        cache.put(task.file_hash, task.rules_hash, AGENT_ANALYZER, issues)
        files_processed += 1

    final_issues = factory.finalize(all_issues, disabled_rules=cfg.disabled_rules)
    score = ScoreCalculator().calculate(final_issues)
    duration_ms = int((time_module.time() - start_time) * 1000)

    cache.log_llm_call(
        model=AGENT_ANALYZER,
        pack=plan.pack_name,
        files=[str(p) for p in report_paths],
        prompt_tokens=0,
        completion_tokens=0,
        duration_ms=duration_ms,
        issues_found=len(final_issues),
        cost_usd=0.0,
    )

    for warning in warnings:
        console.warning(warning, err=True)

    result = AnalysisResult(
        issues=final_issues,
        score=score,
        meta={
            "files_analyzed": files_processed,
            "cache_hits": 0,
            "llm_calls": 0,
            "duration_ms": duration_ms,
            "cost_usd": 0.0,
            "analyzer": AGENT_ANALYZER,
        },
    )

    formatter = get_formatter(format)
    formatted = formatter.format(result)

    if output:
        output.write_text(formatted)
        if not quiet:
            console.success(f"Output written to {output}")
    else:
        print(formatted, end="")


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
        # None means all packs enabled, otherwise check membership
        enabled = cfg.packs is None or pack.name in cfg.packs
        status = "enabled" if enabled else "disabled"
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
    """Clear cached results. Clears all entries, or only entries older than N days if --older is provided."""
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import DEFAULT_CACHE_DB

    cache = SQLiteCache(Path(DEFAULT_CACHE_DB), ttl_hours=168)

    hours = older * 24 if older is not None else None
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
    Also offers to create agent skills if .claude, .codex, or .gemini folders exist.
    """
    config_path = path / "dino.yaml"

    if config_path.exists() and not force:
        console.error(f"Config already exists: {config_path}")
        console.print("Use --force to overwrite", style="dim")
        raise typer.Exit(1)

    default_config = """\
# Dinocheck - Your vibe coding companion
# https://github.com/diegogm/dinocheck

# Analysis mode:
#   agent (default): your AI coding agent performs the review via
#                    'dino brief' + 'dino report'. Zero config, no API keys.
#   api:             'dino check' calls an LLM API directly (CI / headless).
mode: agent

# All rule packs are enabled by default.
# To exclude specific packs, uncomment and add to exclude_packs:
# exclude_packs:
#   - vue
#   - django

# Response language for issue explanations
language: en

# --- API mode settings (only used when mode: api) ---
# model: openai/gpt-5.2-codex  # Or: anthropic/claude-3-5-sonnet, ollama/llama3
# base_url: https://api.example.com/v1  # Custom OpenAI-compatible endpoint
# max_llm_calls: 10  # Analysis budget (max LLM calls per run)

# Analyze only specific directories (default: current directory)
# include_paths:
#   - src/
#   - lib/

# Exclude paths from analysis (glob patterns)
# exclude_paths:
#   - migrations
#   - tests/fixtures
#   - "*.generated.py"

# Disable specific rules (by ID)
# disabled_rules:
#   - python/some-rule-id
"""

    config_path.write_text(default_config)
    console.success(f"Created config: {config_path}")

    # Offer to create skills for detected agents
    agent_configs = [
        ("Claude Code", "claude", path / ".claude"),
        ("OpenAI Codex", "codex", path / ".codex"),
        ("Gemini CLI", "gemini", path / ".gemini"),
    ]

    for agent_name, agent, agent_dir in agent_configs:
        if agent_dir.is_dir():
            create_skill = typer.confirm(
                f"\nDetected {agent_dir.name} folder. Create a {agent_name} skill for dinocheck?",
                default=True,
            )
            if create_skill:
                _create_skill(agent, agent_dir, force)


@app.command()
def skill(
    path: Annotated[
        Path,
        typer.Argument(help="Directory to create skill in"),
    ] = Path("."),
    agent: Annotated[
        str | None,
        typer.Option(
            "--agent",
            "-a",
            help="Specific agent: claude, codex, or gemini",
            click_type=click.Choice(["claude", "codex", "gemini"]),
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing skill",
        ),
    ] = False,
) -> None:
    """Create agent skill for Claude Code, Codex, or Gemini CLI.

    Creates a skill file that allows AI coding agents to use dinocheck
    for code review. The skill is created in the agent's configuration folder.

    Examples:
        dino skill                    # Create for all detected agents
        dino skill --agent claude     # Create only for Claude Code
        dino skill --agent codex      # Create only for OpenAI Codex
        dino skill --agent gemini     # Create only for Gemini CLI
        dino skill --force            # Overwrite existing skills
    """
    agents_found = []
    agents_created = []

    # Define agent configurations
    agent_dirs = {
        "claude": path / ".claude",
        "codex": path / ".codex",
        "gemini": path / ".gemini",
    }

    if agent:
        # Specific agent requested
        agent_dir = agent_dirs[agent]
        if not agent_dir.is_dir():
            console.error(f"Agent folder not found: {agent_dir}")
            console.print(f"Create it with: mkdir {agent_dir}", style="dim")
            raise typer.Exit(1)
        if _create_skill(agent, agent_dir, force):
            agents_created.append(agent)
    else:
        # Auto-detect agents
        for agent_name, agent_dir in agent_dirs.items():
            if agent_dir.is_dir():
                agents_found.append(agent_name)
                if _create_skill(agent_name, agent_dir, force):
                    agents_created.append(agent_name)

        if not agents_found:
            console.warning("No agent folders detected (.claude, .codex, .gemini)")
            console.print("Create one first or use --agent to specify", style="dim")
            raise typer.Exit(1)

    if agents_created:
        console.success(f"Created skills for: {', '.join(agents_created)}")
    elif agents_found:
        console.info("All skills already exist. Use --force to overwrite.")


def _create_skill(agent: str, agent_dir: Path, force: bool) -> bool:
    """Create an agent skill from the packaged template. Returns True if created."""
    from dinocheck.skills.loader import SkillTemplates

    skill_dir = agent_dir / "skills" / "dinocheck"
    skill_file = skill_dir / "SKILL.md"

    if skill_file.exists() and not force:
        return False

    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(SkillTemplates.get(agent), encoding="utf-8")
    console.print(f"  Created: {skill_file}", style="dim")
    return True


@app.command()
def version() -> None:
    """Show Dinocheck version information."""
    console.print(f"Dinocheck v{__version__}", style="bold cyan")
    console.print("Your vibe coding companion", style="dim")


if __name__ == "__main__":
    app()
