"""Deterministic analysis planning: discovery, rule triggering, cache lookup.

The planner runs everything that happens *before* semantic analysis. Its
output (AnalysisPlan) is what the host coding agent executes via
`dino brief` / `dino report`.
"""

from collections.abc import Callable
from pathlib import Path

from dinocheck.core.config import DinocheckConfig
from dinocheck.core.interfaces import Cache, WorkspaceScanner
from dinocheck.core.logging import get_logger
from dinocheck.core.types import AnalysisPlan, FileAnalysisTask, Rule
from dinocheck.core.workspace import GitWorkspaceScanner
from dinocheck.packs.loader import PackCompositor
from dinocheck.utils.hashing import ContentHasher

logger = get_logger()

# Type for progress callback: (step_name, details) -> None
ProgressCallback = Callable[[str, str], None]


class AnalysisPlanner:
    """Plans an analysis run.

    Responsibilities:
    1. Resolve paths (include_paths from config when using the default path)
    2. Compose rule packs
    3. Discover files to analyze
    4. Match triggered rules per file (file patterns + code patterns)
    5. Resolve cache hits for the given analyzer identity
    """

    def __init__(
        self,
        config: DinocheckConfig,
        cache: Cache,
        analyzer: str,
        workspace: WorkspaceScanner | None = None,
    ):
        self.config = config
        self.cache = cache
        self.analyzer = analyzer
        self.workspace = workspace or GitWorkspaceScanner(exclude_patterns=config.exclude_paths)
        self.compositor = PackCompositor()

    def plan(
        self,
        paths: list[Path],
        rule_filter: list[str] | None = None,
        on_progress: ProgressCallback | None = None,
        diff_only: bool = False,
        no_cache: bool = False,
    ) -> AnalysisPlan:
        """Build the analysis plan for the given paths."""

        def progress(step: str, details: str = "") -> None:
            if on_progress:
                on_progress(step, details)

        # 1. Apply include_paths from config when using default path
        if paths == [Path(".")] and self.config.include_paths:
            paths = [Path(p) for p in self.config.include_paths]
            logger.debug("Using include_paths from config: %s", [str(p) for p in paths])

        # 2. Compose packs
        pack_desc = ", ".join(self.config.packs) if self.config.packs else "all"
        progress("compose_packs", f"Loading packs: {pack_desc}")
        composed_pack = self.compositor.compose(self.config.packs, self.config.exclude_packs)
        progress("compose_packs", f"Loaded {len(composed_pack.rules)} rules")
        logger.info("Loaded %d rules from packs: %s", len(composed_pack.rules), composed_pack.name)
        for rule in composed_pack.rules:
            logger.debug("  Rule: %s (%s) - %s", rule.id, rule.level.value, rule.name)

        # 3. Discover files
        scan_paths = [] if diff_only else paths
        progress(
            "discover_files",
            f"Scanning {'changed files' if diff_only else f'{len(paths)} path(s)'}...",
        )
        files = list(self.workspace.discover(scan_paths, diff_only=diff_only))
        progress("discover_files", f"Found {len(files)} file(s) to analyze")
        logger.info("Discovered %d file(s) to analyze", len(files))
        for f in files:
            logger.debug("  File: %s (%d lines)", f.path, f.content.count("\n") + 1)

        plan = AnalysisPlan(pack_name=composed_pack.name, files_total=len(files))

        # 4. Match rules per file and resolve cache
        cache_status = "disabled" if no_cache else "checking"
        progress("check_cache", f"Cache {cache_status}, filtering rules...")

        for file_ctx in files:
            applicable_rules = composed_pack.get_rules_for_file(file_ctx.path, file_ctx.content)

            # Apply rule_filter early to avoid unnecessary analysis
            if rule_filter:
                applicable_rules = [
                    r for r in applicable_rules if any(f in r.id for f in rule_filter)
                ]

            rules_count = len(applicable_rules)

            if rules_count == 0:
                progress("file_skip", f"{file_ctx.path} → 0 rules, skipped")
                logger.debug("SKIP (no rules): %s", file_ctx.path)
                plan.skipped_no_rules += 1
                continue

            file_hash = ContentHasher.hash_content(file_ctx.content)
            rules_hash = self._hash_rules(applicable_rules)

            if not no_cache:
                cached = self.cache.get(file_hash, rules_hash, self.analyzer)
                if cached is not None:
                    progress("file_cache", f"{file_ctx.path} → {rules_count} rules, cached")
                    logger.debug(
                        "Cache HIT: %s (hash=%s, %d issues)",
                        file_ctx.path,
                        file_hash[:8],
                        len(cached),
                    )
                    plan.cached_issues.extend(cached)
                    plan.cache_hits += 1
                    continue

            progress("file_analyze", f"{file_ctx.path} → {rules_count} rules, will analyze")
            logger.debug("Cache MISS: %s (hash=%s)", file_ctx.path, file_hash[:8])
            plan.tasks.append(
                FileAnalysisTask(
                    file_ctx=file_ctx,
                    rules=applicable_rules,
                    file_hash=file_hash,
                    rules_hash=rules_hash,
                )
            )

        logger.info(
            "Files: %d skipped (no rules), %d cached, %d to analyze",
            plan.skipped_no_rules,
            plan.cache_hits,
            len(plan.tasks),
        )

        return plan

    @staticmethod
    def _hash_rules(rules: list[Rule]) -> str:
        """Hash a rule set for cache keying."""
        return ContentHasher.hash_rules([r.id for r in rules])
