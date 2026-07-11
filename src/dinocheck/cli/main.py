"""Dinocheck CLI entry point.

Dinocheck is a vibe coding companion - an agent-native code critic. Your AI
coding agent performs the analysis through `dino brief` and `dino report`;
dinocheck selects the files and rules, then validates, scores, and caches
the findings. It never modifies code and needs no API keys.
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
    help="Dinocheck: Your vibe coding companion - agent-native AI code critic",
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

QuietOption = Annotated[
    bool,
    typer.Option(
        "-q",
        "--quiet",
        help="Suppress non-essential output",
    ),
]

DebugOption = Annotated[
    bool,
    typer.Option(
        "--debug",
        help="Write detailed debug log to dino.log",
    ),
]


def _setup_debug(debug: bool) -> None:
    """Enable debug logging when requested."""
    if debug:
        from dinocheck.core.logging import setup_logger

        setup_logger(debug=True)
        console.info("Debug mode enabled - writing to dino.log", err=True)


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
    debug: DebugOption = False,
) -> None:
    """Generate a review brief for the host coding agent (step 1).

    Selects the files to review and the rules that apply to each, and emits
    the instructions the agent needs to perform the analysis itself. Submit
    the agent's findings afterwards with 'dino report'.

    Examples:
        dino brief --diff -o .dinocheck/brief.md  # Changed files only
        dino brief src/                           # Specific directory
        dino brief --format json                  # Machine-readable brief
    """
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import AGENT_ANALYZER, DEFAULT_CACHE_DB
    from dinocheck.core.planner import AnalysisPlanner
    from dinocheck.llm.prompts import BriefBuilder

    _setup_debug(debug)
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
    fail_on: Annotated[
        str | None,
        typer.Option(
            "--fail-on",
            help="Exit with code 1 if any issue at this level or above is found",
            click_type=click.Choice(["blocker", "critical", "major", "minor", "info"]),
        ),
    ] = None,
    config: ConfigOption = None,
    quiet: QuietOption = False,
    debug: DebugOption = False,
) -> None:
    """Validate and score the host agent's findings (step 2).

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

    _setup_debug(debug)
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
            response,
            task.file_ctx,
            plan.pack_name,
            source="agent",
            allowed_rule_ids={rule.id for rule in task.rules},
        )
        warnings.extend(issue_warnings)
        all_issues.extend(issues)
        cache.put(task.file_hash, task.rules_hash, AGENT_ANALYZER, issues)
        files_processed += 1

    final_issues = factory.finalize(all_issues, disabled_rules=cfg.disabled_rules)
    score = ScoreCalculator().calculate(final_issues)
    duration_ms = int((time_module.time() - start_time) * 1000)

    cache.log_run(
        analyzer=AGENT_ANALYZER,
        pack=plan.pack_name,
        files=[str(p) for p in report_paths],
        duration_ms=duration_ms,
        issues_found=len(final_issues),
    )

    for warning in warnings:
        console.warning(warning, err=True)

    result = AnalysisResult(
        issues=final_issues,
        score=score,
        meta={
            "files_analyzed": files_processed,
            "duration_ms": duration_ms,
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

    if fail_on:
        from dinocheck.core.issue_factory import SEVERITY_ORDER

        threshold = SEVERITY_ORDER.index(fail_on)
        failing = [i for i in final_issues if SEVERITY_ORDER.index(i.level.value) <= threshold]
        if failing:
            console.error(
                f"{len(failing)} issue(s) at level '{fail_on}' or above",
            )
            raise typer.Exit(1)


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
logs_app = typer.Typer(help="View analysis run history")
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
    """List recent analysis runs."""
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import DEFAULT_CACHE_DB

    cache = SQLiteCache(Path(DEFAULT_CACHE_DB), ttl_hours=168)
    runs = cache.get_runs(limit)

    if not runs:
        console.info("No analysis runs logged yet")
        return

    table = console.table(
        title="Recent Analysis Runs",
        columns=[
            ("ID", "dim"),
            ("Timestamp", ""),
            ("Analyzer", "cyan"),
            ("Pack", ""),
            ("Files", ""),
            ("Duration", ""),
            ("Issues", "yellow"),
        ],
    )

    for run in runs:
        table.add_row(
            run.id[:8],
            run.timestamp[:19],
            run.analyzer,
            run.pack,
            str(len(run.files)),
            f"{run.duration_ms}ms",
            str(run.issues_found),
        )

    console.print_table(table)


@logs_app.command("show")
def logs_show(
    run_id: Annotated[str, typer.Argument(help="Run ID (partial match)")],
) -> None:
    """Show details of a specific analysis run."""
    from dinocheck.core.cache import SQLiteCache
    from dinocheck.core.config import DEFAULT_CACHE_DB

    cache = SQLiteCache(Path(DEFAULT_CACHE_DB), ttl_hours=168)
    run = cache.get_run(run_id)

    if not run:
        console.error(f"Run not found: {run_id}")
        raise typer.Exit(2)

    console.header(f"Analysis Run {run.id[:12]}...")

    console.status_line("Timestamp", run.timestamp)
    console.status_line("Analyzer", run.analyzer, style="cyan")
    console.status_line("Pack", run.pack)
    console.status_line("Duration", f"{run.duration_ms}ms")
    console.status_line("Issues found", str(run.issues_found), style="yellow")

    console.print()
    console.print("Files analyzed:", style="bold")
    for f in run.files:
        console.print(f"  - {f}", style="dim")


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
#
# Dinocheck is agent-native: your AI coding agent performs the review via
# 'dino brief' + 'dino report'. No API keys, no model configuration.

# All rule packs are enabled by default.
# To exclude specific packs, uncomment and add to exclude_packs:
# exclude_packs:
#   - vue
#   - django

# Response language for issue explanations
language: en

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

    # Keep the local cache out of version control
    gitignore = path / ".gitignore"
    ignore_entry = ".dinocheck/"
    if gitignore.exists():
        lines = gitignore.read_text(encoding="utf-8").splitlines()
        if ignore_entry not in (line.strip() for line in lines):
            with gitignore.open("a", encoding="utf-8") as f:
                f.write(f"\n# Dinocheck local cache\n{ignore_entry}\n")
            console.print(f"  Added {ignore_entry} to .gitignore", style="dim")
    else:
        gitignore.write_text(f"# Dinocheck local cache\n{ignore_entry}\n", encoding="utf-8")
        console.print(f"  Created .gitignore with {ignore_entry}", style="dim")

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
