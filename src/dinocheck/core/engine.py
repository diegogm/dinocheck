"""Main analysis orchestration engine."""

import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dinocheck.core.cache import SQLiteCache
from dinocheck.core.config import DEFAULT_CACHE_DB, DinocheckConfig
from dinocheck.core.interfaces import LLMProvider
from dinocheck.core.logging import get_logger
from dinocheck.core.scoring import ScoreCalculator
from dinocheck.core.types import AnalysisResult, FileContext, Issue, IssueLevel, Location, Rule
from dinocheck.core.workspace import GitWorkspaceScanner
from dinocheck.llm.prompts import CriticPromptBuilder
from dinocheck.llm.schemas import CriticResponse
from dinocheck.packs.loader import ComposedPack, PackCompositor
from dinocheck.utils.code import CodeExtractor
from dinocheck.utils.hashing import ContentHasher

logger = get_logger()

# Type for progress callback: (step_name, details) -> None
ProgressCallback = Callable[[str, str], None]

# Hardcoded limits (no longer configurable)
MAX_TOKENS_PER_CALL = 4096
MAX_ISSUES_PER_FILE = 10


class Engine:
    """Orchestrates the complete analysis pipeline.

    This is the main entry point for running code analysis. It:
    1. Discovers files to analyze
    2. Checks cache for previously analyzed files
    3. Sends uncached files to LLM for analysis
    4. Collects and deduplicates issues
    5. Calculates score
    """

    def __init__(self, config: DinocheckConfig):
        self.config = config
        self.workspace = GitWorkspaceScanner()
        self.scorer = ScoreCalculator()
        self.compositor = PackCompositor()

        # Initialize cache (always enabled, using default location)
        cache_path = Path(DEFAULT_CACHE_DB)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = SQLiteCache(cache_path, ttl_hours=168)

        # Initialize provider
        self.provider = self._create_provider()

    def _create_provider(self) -> LLMProvider:
        """Create LLM provider based on config."""
        from dinocheck.providers import LiteLLMProvider

        api_key = os.environ.get(self.config.api_key_env) if self.config.api_key_env else None

        return LiteLLMProvider(
            model=self.config.model,
            api_key=api_key,
            cache_db=Path(DEFAULT_CACHE_DB),
        )

    def analyze(
        self,
        paths: list[Path],
        rule_filter: list[str] | None = None,
        on_progress: ProgressCallback | None = None,
        diff_only: bool = False,
        no_cache: bool = False,
    ) -> AnalysisResult:
        """Run complete analysis pipeline.

        This is a synchronous method that uses ThreadPoolExecutor internally
        for concurrent LLM calls. Use asyncio.to_thread() if you need async.

        Args:
            paths: Files or directories to analyze
            rule_filter: Optional list of rule IDs to filter
            on_progress: Optional callback for progress updates (step, details)
            diff_only: If True, only analyze files with local git changes
            no_cache: If True, skip cache lookup and re-analyze all files

        Returns:
            AnalysisResult with issues, score, and metadata
        """
        start_time = time.time()
        logger.info("=" * 60)
        logger.info("DINOCRIT ANALYSIS STARTED")
        logger.info("=" * 60)
        logger.debug(
            "Config: model=%s, packs=%s, language=%s",
            self.config.model,
            self.config.packs,
            self.config.language,
        )
        logger.debug("Paths to analyze: %s, diff_only=%s", [str(p) for p in paths], diff_only)

        def progress(step: str, details: str = "") -> None:
            if on_progress:
                on_progress(step, details)

        # 1. Compose packs
        progress("compose_packs", f"Loading packs: {', '.join(self.config.packs)}")
        composed_pack = self.compositor.compose(self.config.packs)
        progress("compose_packs", f"Loaded {len(composed_pack.rules)} rules")
        logger.info(
            "Loaded %d rules from packs: %s", len(composed_pack.rules), ", ".join(self.config.packs)
        )
        for rule in composed_pack.rules:
            logger.debug("  Rule: %s (%s) - %s", rule.id, rule.level.value, rule.name)

        # 2. Discover files to analyze
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

        if not files:
            logger.info("No files to analyze - returning early")
            return AnalysisResult(
                issues=[],
                score=100,
                meta={
                    "files_analyzed": 0,
                    "cache_hits": 0,
                    "llm_calls": 0,
                    "duration_ms": int((time.time() - start_time) * 1000),
                    "cost_usd": 0.0,
                },
            )

        # 3. Check cache, filter rules, and collect files to analyze
        cache_status = "disabled" if no_cache else "checking"
        progress("check_cache", f"Cache {cache_status}, filtering rules...")
        all_issues: list[Issue] = []
        uncached_files: list[FileContext] = []
        uncached_rules: dict[str, list[Rule]] = {}  # path -> applicable rules
        cache_hits = 0
        skipped_no_rules = 0

        for file_ctx in files:
            # First check how many rules apply to this file
            applicable_rules = composed_pack.get_rules_for_file(file_ctx.path, file_ctx.content)

            # Apply rule_filter early to avoid unnecessary LLM calls
            if rule_filter:
                applicable_rules = [
                    r for r in applicable_rules if any(f in r.id for f in rule_filter)
                ]

            rules_count = len(applicable_rules)

            if rules_count == 0:
                progress("file_skip", f"{file_ctx.path} → 0 rules, skipped")
                logger.debug("SKIP (no rules): %s", file_ctx.path)
                skipped_no_rules += 1
                continue

            file_hash = ContentHasher.hash_content(file_ctx.content)
            rules_hash = ContentHasher.hash_rules([r.id for r in applicable_rules])

            # Check cache only if not disabled
            if not no_cache:
                cached = self.cache.get(file_hash, composed_pack.version, rules_hash)
                if cached is not None:
                    progress("file_cache", f"{file_ctx.path} → {rules_count} rules, cached")
                    logger.debug(
                        "Cache HIT: %s (hash=%s, %d issues)",
                        file_ctx.path,
                        file_hash[:8],
                        len(cached),
                    )
                    all_issues.extend(cached)
                    cache_hits += 1
                    continue

            progress("file_analyze", f"{file_ctx.path} → {rules_count} rules, will analyze")
            logger.debug("Cache MISS: %s (hash=%s)", file_ctx.path, file_hash[:8])
            uncached_files.append(file_ctx)
            uncached_rules[str(file_ctx.path)] = applicable_rules

        logger.info(
            "Files: %d skipped (no rules), %d cached, %d to analyze",
            skipped_no_rules,
            cache_hits,
            len(uncached_files),
        )

        # 4. Analyze uncached files with LLM using ThreadPool for concurrency
        progress("analyze_files", f"Analyzing {len(uncached_files)} uncached file(s)...")
        llm_calls = 0
        total_cost = 0.0
        max_calls = self.config.max_llm_calls
        max_workers = min(self.provider.max_concurrent, max_calls, len(uncached_files))

        if uncached_files and max_calls > 0:
            files_to_analyze = uncached_files[:max_calls]

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all analysis tasks with pre-calculated rules
                future_to_file = {
                    executor.submit(
                        self._analyze_file_sync,
                        file_ctx,
                        composed_pack,
                        uncached_rules[str(file_ctx.path)],
                    ): file_ctx
                    for file_ctx in files_to_analyze
                }

                # Process results as they complete
                for future in as_completed(future_to_file):
                    file_ctx = future_to_file[future]
                    try:
                        issues, cost_usd = future.result()
                        llm_calls += 1
                        total_cost += cost_usd

                        # Report progress
                        issues_text = f"{len(issues)} issues" if issues else "ok"
                        progress(
                            "llm_result",
                            f"[{llm_calls}/{len(files_to_analyze)}] {file_ctx.path} → {issues_text}",
                        )

                        logger.info(
                            "LLM analyzed %s: found %d issue(s)", file_ctx.path, len(issues)
                        )
                        for issue in issues:
                            logger.debug(
                                "  Issue: [%s] %s at line %d",
                                issue.level.value,
                                issue.title,
                                issue.location.start_line,
                            )
                        all_issues.extend(issues)

                        # Cache results using the applicable rules hash
                        applicable_rules = uncached_rules[str(file_ctx.path)]
                        file_hash = ContentHasher.hash_content(file_ctx.content)
                        rules_hash = ContentHasher.hash_rules([r.id for r in applicable_rules])
                        self.cache.put(file_hash, composed_pack.version, rules_hash, issues)

                    except Exception:
                        llm_calls += 1
                        progress(
                            "llm_error",
                            f"[{llm_calls}/{len(files_to_analyze)}] {file_ctx.path} → ERROR",
                        )
                        raise

        # 5. Apply rule filter if specified
        if rule_filter:
            progress("filter_rules", f"Filtering by rules: {', '.join(rule_filter)}")
            all_issues = [
                issue for issue in all_issues if any(f in issue.rule_id for f in rule_filter)
            ]

        # 6. Filter out disabled rules
        if self.config.disabled_rules:
            progress(
                "filter_disabled", f"Filtering {len(self.config.disabled_rules)} disabled rule(s)"
            )
            all_issues = [
                issue for issue in all_issues if issue.rule_id not in self.config.disabled_rules
            ]

        # 7. Deduplicate issues
        progress("deduplicate", f"Deduplicating {len(all_issues)} issue(s)...")
        all_issues = self._deduplicate(all_issues)

        # 8. Limit issues per file
        progress("limit_issues", f"Limiting to {MAX_ISSUES_PER_FILE} issues per file...")
        all_issues = self._limit_per_file(all_issues)

        # 9. Calculate score
        progress("calculate_score", f"Calculating score for {len(all_issues)} issue(s)...")
        score = self.scorer.calculate(all_issues)

        duration_ms = int((time.time() - start_time) * 1000)
        progress("complete", f"Analysis complete in {duration_ms}ms")

        logger.info("=" * 60)
        logger.info("ANALYSIS COMPLETE")
        logger.info("=" * 60)
        logger.info("Duration: %dms", duration_ms)
        logger.info(
            "Files analyzed: %d (cache hits: %d, LLM calls: %d)", len(files), cache_hits, llm_calls
        )
        logger.info("Issues found: %d", len(all_issues))
        logger.info("Score: %d/100", score)

        return AnalysisResult(
            issues=all_issues,
            score=score,
            meta={
                "files_analyzed": len(files),
                "cache_hits": cache_hits,
                "llm_calls": llm_calls,
                "duration_ms": duration_ms,
                "cost_usd": total_cost,
            },
        )

    def _analyze_file_sync(
        self,
        file_ctx: FileContext,
        composed_pack: ComposedPack,
        rules: list[Rule] | None = None,
    ) -> tuple[list[Issue], float]:
        """Analyze a single file using LLM (synchronous, thread-safe).

        Args:
            file_ctx: File context with path and content
            composed_pack: The composed pack being used
            rules: Pre-calculated applicable rules (optional, will calculate if not provided)

        Returns:
            Tuple of (issues, cost_usd)
        """
        logger.debug("-" * 40)
        logger.debug("Analyzing file: %s", file_ctx.path)

        # Use pre-calculated rules or calculate them
        if rules is None:
            rules = composed_pack.get_rules_for_file(file_ctx.path, file_ctx.content)

        logger.debug("Applicable rules: %d", len(rules))
        for rule in rules:
            logger.debug("  - %s", rule.id)

        if not rules:
            logger.debug("No applicable rules - skipping file")
            return [], 0.0

        # Build prompts
        prompt = CriticPromptBuilder.build_user_prompt(file_ctx, rules, self.config.language)
        system = CriticPromptBuilder.build_system_prompt(composed_pack.name)
        logger.debug("Prompt length: %d chars", len(prompt))

        # Call LLM with structured output (synchronous)
        logger.debug("Calling LLM: %s", self.config.model)
        start_time = time.time()
        result = self.provider.complete_structured_sync(
            prompt=prompt,
            response_schema=CriticResponse,
            system=system,
        )
        response = CriticResponse.model_validate(result.model_dump())
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug("LLM response received in %dms", duration_ms)

        # Convert response to issues
        issues = self._response_to_issues(response, file_ctx, composed_pack.name)

        # Log the call and get cost
        cost_usd = self.cache.log_llm_call(
            model=self.config.model,
            pack=composed_pack.name,
            files=[str(file_ctx.path)],
            prompt_tokens=self.provider.estimate_tokens(prompt),
            completion_tokens=self.provider.estimate_tokens(str(response.model_dump())),
            duration_ms=duration_ms,
            issues_found=len(issues),
        )

        return issues, cost_usd

    def _response_to_issues(
        self,
        response: CriticResponse,
        file_ctx: FileContext,
        pack_name: str,
    ) -> list[Issue]:
        """Convert LLM response to Issue objects."""
        issues = []

        for critic_issue in response.issues:
            try:
                start_line = critic_issue.location.start_line
                end_line = critic_issue.location.end_line

                # Extract code snippet and context
                snippet = CodeExtractor.extract_snippet(file_ctx.content, start_line, end_line)
                context = CodeExtractor.extract_context(file_ctx.content, start_line)

                issue = Issue(
                    rule_id=critic_issue.rule_id,
                    level=IssueLevel(critic_issue.level),
                    location=Location(
                        path=file_ctx.path,
                        start_line=start_line,
                        end_line=end_line,
                    ),
                    title=critic_issue.title,
                    why=critic_issue.why,
                    do=critic_issue.do,
                    pack=pack_name,
                    source="llm",
                    confidence=critic_issue.confidence,
                    tags=critic_issue.tags,
                    snippet=snippet,
                    context=context,
                )
                issues.append(issue)
            except Exception:
                continue

        return issues

    def _deduplicate(self, issues: list[Issue]) -> list[Issue]:
        """Remove duplicate issues by issue_id."""
        seen = set()
        unique = []
        for issue in issues:
            if issue.issue_id not in seen:
                seen.add(issue.issue_id)
                unique.append(issue)
        return unique

    def _limit_per_file(self, issues: list[Issue]) -> list[Issue]:
        """Limit issues per file."""
        by_file: dict[str, list[Issue]] = {}
        for issue in issues:
            path = str(issue.location.path)
            if path not in by_file:
                by_file[path] = []
            by_file[path].append(issue)

        limited = []
        for file_issues in by_file.values():
            # Sort by severity and take top N
            severity_order = ["blocker", "critical", "major", "minor", "info"]
            file_issues.sort(key=lambda i: severity_order.index(i.level.value))
            limited.extend(file_issues[:MAX_ISSUES_PER_FILE])

        return limited
