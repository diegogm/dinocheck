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
from dinocheck.core.types import AnalysisResult, FileContext, Issue, IssueLevel, Location
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
    5. Calculates score and gate status
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

    async def analyze(
        self,
        paths: list[Path],
        rule_filter: list[str] | None = None,
        on_progress: ProgressCallback | None = None,
        diff_only: bool = False,
    ) -> AnalysisResult:
        """Run complete analysis pipeline.

        Args:
            paths: Files or directories to analyze
            rule_filter: Optional list of rule IDs to filter
            on_progress: Optional callback for progress updates (step, details)
            diff_only: If True, only analyze files with local git changes

        Returns:
            AnalysisResult with issues, score, and metadata
        """
        start_time = time.time()
        logger.info("=" * 60)
        logger.info("DINOCRIT ANALYSIS STARTED")
        logger.info("=" * 60)
        logger.debug("Config: model=%s, packs=%s, language=%s", self.config.model, self.config.packs, self.config.language)
        logger.debug("Paths to analyze: %s, diff_only=%s", [str(p) for p in paths], diff_only)

        def progress(step: str, details: str = "") -> None:
            if on_progress:
                on_progress(step, details)

        # 1. Compose packs
        progress("compose_packs", f"Loading packs: {', '.join(self.config.packs)}")
        composed_pack = self.compositor.compose(self.config.packs)
        progress("compose_packs", f"Loaded {len(composed_pack.rules)} rules")
        logger.info("Loaded %d rules from packs: %s", len(composed_pack.rules), ", ".join(self.config.packs))
        for rule in composed_pack.rules:
            logger.debug("  Rule: %s (%s) - %s", rule.id, rule.level.value, rule.name)

        # 2. Discover files to analyze
        scan_paths = [] if diff_only else paths
        progress("discover_files", f"Scanning {'changed files' if diff_only else f'{len(paths)} path(s)'}...")
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
                gate_passed=True,
                fail_reasons=[],
                meta={
                    "files_analyzed": 0,
                    "cache_hits": 0,
                    "llm_calls": 0,
                    "duration_ms": int((time.time() - start_time) * 1000),
                },
            )

        # 3. Check cache and collect uncached files
        progress("check_cache", "Checking cache for previous results...")
        all_issues: list[Issue] = []
        uncached_files: list[FileContext] = []
        cache_hits = 0

        for file_ctx in files:
            file_hash = ContentHasher.hash_content(file_ctx.content)
            rules_hash = ContentHasher.hash_rules([r.id for r in composed_pack.rules])

            cached = self.cache.get(file_hash, composed_pack.version, rules_hash)
            if cached is not None:
                logger.debug("Cache HIT: %s (hash=%s, %d issues)", file_ctx.path, file_hash[:8], len(cached))
                all_issues.extend(cached)
                cache_hits += 1
                continue

            logger.debug("Cache MISS: %s (hash=%s)", file_ctx.path, file_hash[:8])
            uncached_files.append(file_ctx)

        logger.info("Cache: %d hits, %d misses", cache_hits, len(uncached_files))

        # 4. Analyze uncached files with LLM using ThreadPool for concurrency
        progress("analyze_files", f"Analyzing {len(uncached_files)} uncached file(s)...")
        llm_calls = 0
        max_calls = self.config.max_llm_calls
        max_workers = min(self.provider.max_concurrent, max_calls, len(uncached_files))

        if uncached_files and max_calls > 0:
            files_to_analyze = uncached_files[:max_calls]

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all analysis tasks
                future_to_file = {
                    executor.submit(self._analyze_file_sync, file_ctx, composed_pack): file_ctx
                    for file_ctx in files_to_analyze
                }

                # Process results as they complete
                for future in as_completed(future_to_file):
                    file_ctx = future_to_file[future]
                    try:
                        issues = future.result()
                        logger.info("LLM analyzed %s: found %d issue(s)", file_ctx.path, len(issues))
                        for issue in issues:
                            logger.debug("  Issue: [%s] %s at line %d", issue.level.value, issue.title, issue.location.start_line)
                        all_issues.extend(issues)
                        llm_calls += 1

                        # Cache results
                        file_hash = ContentHasher.hash_content(file_ctx.content)
                        rules_hash = ContentHasher.hash_rules([r.id for r in composed_pack.rules])
                        self.cache.put(file_hash, composed_pack.version, rules_hash, issues)

                    except Exception as e:
                        logger.warning("LLM error for %s: %s", file_ctx.path, e)

        # 5. Apply rule filter if specified
        if rule_filter:
            progress("filter_rules", f"Filtering by rules: {', '.join(rule_filter)}")
            all_issues = [
                issue for issue in all_issues
                if any(f in issue.rule_id for f in rule_filter)
            ]

        # 6. Filter out disabled rules
        if self.config.disabled_rules:
            progress("filter_disabled", f"Filtering {len(self.config.disabled_rules)} disabled rule(s)")
            all_issues = [
                issue for issue in all_issues
                if issue.rule_id not in self.config.disabled_rules
            ]

        # 7. Deduplicate issues
        progress("deduplicate", f"Deduplicating {len(all_issues)} issue(s)...")
        all_issues = self._deduplicate(all_issues)

        # 8. Limit issues per file
        progress("limit_issues", f"Limiting to {MAX_ISSUES_PER_FILE} issues per file...")
        all_issues = self._limit_per_file(all_issues)

        # 9. Calculate score and check gate
        progress("calculate_score", f"Calculating score for {len(all_issues)} issue(s)...")
        score = self.scorer.calculate(all_issues)
        gate_passed, fail_reasons = self.scorer.check_gate(all_issues)

        duration_ms = int((time.time() - start_time) * 1000)
        progress("complete", f"Analysis complete in {duration_ms}ms")

        logger.info("=" * 60)
        logger.info("ANALYSIS COMPLETE")
        logger.info("=" * 60)
        logger.info("Duration: %dms", duration_ms)
        logger.info("Files analyzed: %d (cache hits: %d, LLM calls: %d)", len(files), cache_hits, llm_calls)
        logger.info("Issues found: %d", len(all_issues))
        logger.info("Score: %d/100 | Gate: %s", score, "PASSED" if gate_passed else "FAILED")
        if fail_reasons:
            for reason in fail_reasons:
                logger.info("  Fail reason: %s", reason)

        return AnalysisResult(
            issues=all_issues,
            score=score,
            gate_passed=gate_passed,
            fail_reasons=fail_reasons,
            meta={
                "files_analyzed": len(files),
                "cache_hits": cache_hits,
                "llm_calls": llm_calls,
                "duration_ms": duration_ms,
            },
        )

    def _analyze_file_sync(
        self,
        file_ctx: FileContext,
        composed_pack: ComposedPack,
    ) -> list[Issue]:
        """Analyze a single file using LLM (synchronous, thread-safe)."""
        logger.debug("-" * 40)
        logger.debug("Analyzing file: %s", file_ctx.path)

        # Get applicable rules for this file
        rules = composed_pack.get_rules_for_file(file_ctx.path, file_ctx.content)
        logger.debug("Applicable rules: %d", len(rules))
        for rule in rules:
            logger.debug("  - %s", rule.id)

        if not rules:
            logger.debug("No applicable rules - skipping file")
            return []

        # Build prompts
        prompt = CriticPromptBuilder.build_user_prompt(
            file_ctx, rules, self.config.language
        )
        system = CriticPromptBuilder.build_system_prompt(composed_pack.name)
        logger.debug("Prompt length: %d chars", len(prompt))

        try:
            # Call LLM with structured output (synchronous)
            logger.debug("Calling LLM: %s", self.config.model)
            start_time = time.time()
            result = self.provider.complete_structured_sync(
                prompt=prompt,
                response_schema=CriticResponse,
                system=system,
                max_tokens=MAX_TOKENS_PER_CALL,
                temperature=0.1,
            )
            response = CriticResponse.model_validate(result.model_dump())
            duration_ms = int((time.time() - start_time) * 1000)
            logger.debug("LLM response received in %dms", duration_ms)

            # Convert response to issues
            issues = self._response_to_issues(response, file_ctx, composed_pack.name)

            # Log the call
            self.cache.log_llm_call(
                model=self.config.model,
                pack=composed_pack.name,
                files=[str(file_ctx.path)],
                prompt_tokens=self.provider.estimate_tokens(prompt),
                completion_tokens=self.provider.estimate_tokens(str(response.model_dump())),
                duration_ms=duration_ms,
                issues_found=len(issues),
            )

            return issues

        except Exception:
            return []

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
                snippet = CodeExtractor.extract_snippet(
                    file_ctx.content, start_line, end_line
                )
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
            file_issues.sort(
                key=lambda i: severity_order.index(i.level.value)
            )
            limited.extend(file_issues[:MAX_ISSUES_PER_FILE])

        return limited
