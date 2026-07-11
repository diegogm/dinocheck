"""API-mode analysis engine: executes an analysis plan against an LLM API."""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast

from dinocheck.core.cache import SQLiteCache
from dinocheck.core.config import DEFAULT_CACHE_DB, DinocheckConfig
from dinocheck.core.interfaces import LLMProvider
from dinocheck.core.issue_factory import IssueFactory
from dinocheck.core.logging import get_logger
from dinocheck.core.planner import AnalysisPlanner, ProgressCallback
from dinocheck.core.scoring import ScoreCalculator
from dinocheck.core.types import AnalysisResult, FileAnalysisTask, Issue
from dinocheck.llm.prompts import CriticPromptBuilder
from dinocheck.llm.schemas import CriticResponse

logger = get_logger()


class Engine:
    """Executes the analysis pipeline using an external LLM API.

    The deterministic half (discovery, rule triggering, cache lookup) is
    delegated to AnalysisPlanner; this class drives the LLM calls for the
    plan's pending tasks and post-processes the results. Agent mode uses
    the same planner via `dino brief` / `dino report` instead.
    """

    def __init__(self, config: DinocheckConfig, debug: bool = False):
        self.config = config
        self.debug = debug
        self.scorer = ScoreCalculator()
        self.issue_factory = IssueFactory()

        # Initialize cache (always enabled, using default location)
        cache_path = Path(DEFAULT_CACHE_DB)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = SQLiteCache(cache_path, ttl_hours=168)

        # Results are cached under the model identity so they never mix
        # with agent-mode results
        self.planner = AnalysisPlanner(config, self.cache, analyzer=config.model)

        # Initialize provider
        self.provider = self._create_provider()

    def _create_provider(self) -> LLMProvider:
        """Create LLM provider based on config."""
        from dinocheck.providers import LiteLLMProvider

        api_key = os.environ.get(self.config.api_key_env) if self.config.api_key_env else None

        return LiteLLMProvider(
            model=self.config.model,
            api_key=api_key,
            base_url=self.config.base_url,
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
        logger.info("DINOCHECK ANALYSIS STARTED")
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

        # 1. Plan: discovery, rule triggering, cache lookup
        plan = self.planner.plan(
            paths,
            rule_filter=rule_filter,
            on_progress=on_progress,
            diff_only=diff_only,
            no_cache=no_cache,
        )

        if plan.files_total == 0:
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

        all_issues: list[Issue] = list(plan.cached_issues)

        # 2. Analyze pending tasks with LLM using ThreadPool for concurrency
        progress("analyze_files", f"Analyzing {len(plan.tasks)} uncached file(s)...")
        llm_calls = 0
        total_cost = 0.0
        errors: list[str] = []
        max_calls = self.config.max_llm_calls
        tasks_to_run = plan.tasks[:max_calls]
        files_truncated = len(plan.tasks) - len(tasks_to_run)
        if files_truncated:
            progress(
                "budget_exceeded",
                f"{files_truncated} file(s) skipped: max_llm_calls={max_calls} budget reached",
            )
            logger.warning(
                "Budget reached: %d file(s) not analyzed (max_llm_calls=%d)",
                files_truncated,
                max_calls,
            )
        max_workers = min(self.provider.max_concurrent, max(1, len(tasks_to_run)))

        if tasks_to_run:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_task = {
                    executor.submit(self._analyze_task, task, plan.pack_name): task
                    for task in tasks_to_run
                }

                # Process results as they complete; a single failed file must
                # not discard the results of the others
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    llm_calls += 1
                    try:
                        issues, cost_usd = future.result()
                    except Exception as e:
                        progress(
                            "llm_error",
                            f"[{llm_calls}/{len(tasks_to_run)}] {task.file_ctx.path} → ERROR",
                        )
                        logger.error("LLM analysis failed for %s: %s", task.file_ctx.path, e)
                        errors.append(f"{task.file_ctx.path}: {e}")
                        continue

                    total_cost += cost_usd
                    issues_text = f"{len(issues)} issues" if issues else "ok"
                    progress(
                        "llm_result",
                        f"[{llm_calls}/{len(tasks_to_run)}] {task.file_ctx.path} → {issues_text}",
                    )

                    logger.info(
                        "LLM analyzed %s: found %d issue(s)", task.file_ctx.path, len(issues)
                    )
                    for issue in issues:
                        logger.debug(
                            "  Issue: [%s] %s at line %d",
                            issue.level.value,
                            issue.title,
                            issue.location.start_line,
                        )
                    all_issues.extend(issues)

                    self.cache.put(task.file_hash, task.rules_hash, self.config.model, issues)

            if errors and llm_calls == len(errors):
                # Every single call failed - this is a run failure, not noise
                raise RuntimeError(f"All {llm_calls} LLM call(s) failed. First error: {errors[0]}")

        # 3. Post-process: filters, dedupe, per-file limit
        progress("finalize", f"Post-processing {len(all_issues)} issue(s)...")
        all_issues = self.issue_factory.finalize(
            all_issues,
            rule_filter=rule_filter,
            disabled_rules=self.config.disabled_rules,
        )

        # 4. Calculate score
        progress("calculate_score", f"Calculating score for {len(all_issues)} issue(s)...")
        score = self.scorer.calculate(all_issues)

        duration_ms = int((time.time() - start_time) * 1000)
        progress("complete", f"Analysis complete in {duration_ms}ms")

        logger.info("=" * 60)
        logger.info("ANALYSIS COMPLETE")
        logger.info("=" * 60)
        logger.info("Duration: %dms", duration_ms)
        logger.info(
            "Files analyzed: %d (cache hits: %d, LLM calls: %d)",
            plan.files_total,
            plan.cache_hits,
            llm_calls,
        )
        logger.info("Issues found: %d", len(all_issues))
        logger.info("Score: %d/100", score)

        meta: dict[str, Any] = {
            "files_analyzed": plan.files_total,
            "cache_hits": plan.cache_hits,
            "llm_calls": llm_calls,
            "duration_ms": duration_ms,
            "cost_usd": total_cost,
        }
        if files_truncated:
            meta["files_truncated"] = files_truncated
        if errors:
            meta["errors"] = errors

        return AnalysisResult(issues=all_issues, score=score, meta=meta)

    def _analyze_task(self, task: FileAnalysisTask, pack_name: str) -> tuple[list[Issue], float]:
        """Analyze a single planned task using the LLM (synchronous, thread-safe).

        Returns:
            Tuple of (issues, cost_usd)
        """
        file_ctx = task.file_ctx
        logger.debug("-" * 40)
        logger.debug("Analyzing file: %s", file_ctx.path)
        logger.debug("Applicable rules: %d", len(task.rules))
        for rule in task.rules:
            logger.debug("  - %s", rule.id)

        # Build prompts
        prompt = CriticPromptBuilder.build_user_prompt(file_ctx, task.rules, self.config.language)
        system = CriticPromptBuilder.build_system_prompt(pack_name)
        logger.debug("Prompt length: %d chars", len(prompt))

        # Call LLM with structured output (synchronous)
        logger.debug("Calling LLM: %s", self.config.model)
        start_time = time.time()
        completion = self.provider.complete_structured_sync(
            prompt=prompt,
            response_schema=CriticResponse,
            system=system,
        )
        response = cast(CriticResponse, completion.data)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug("LLM response received in %dms", duration_ms)

        # Convert response to issues
        issues, warnings = self.issue_factory.create_issues(response, file_ctx, pack_name)
        for warning in warnings:
            logger.warning("Dropped LLM issue: %s", warning)

        # Log the call using real usage when the provider reports it
        prompt_tokens = (
            completion.prompt_tokens
            if completion.prompt_tokens is not None
            else self.provider.estimate_tokens(prompt)
        )
        completion_tokens = (
            completion.completion_tokens
            if completion.completion_tokens is not None
            else self.provider.estimate_tokens(response.model_dump_json())
        )
        cost_usd = self.cache.log_llm_call(
            model=self.config.model,
            pack=pack_name,
            files=[str(file_ctx.path)],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
            issues_found=len(issues),
            cost_usd=completion.cost_usd,
        )

        return issues, cost_usd
