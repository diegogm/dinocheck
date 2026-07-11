"""Conversion of critic responses into Issue objects, plus filtering helpers."""

from dinocheck.core.types import FileContext, Issue, IssueLevel, Location
from dinocheck.llm.schemas import CriticResponse
from dinocheck.utils.code import CodeExtractor

# Hardcoded limit (not configurable)
MAX_ISSUES_PER_FILE = 10

SEVERITY_ORDER = ["blocker", "critical", "major", "minor", "info"]


class IssueFactory:
    """Builds, filters, deduplicates, and limits Issue objects.

    Used by `dino report` to turn the host agent's findings into issues.
    Invalid entries are never dropped silently - they are returned as
    warnings so callers can surface them.
    """

    def create_issues(
        self,
        response: CriticResponse,
        file_ctx: FileContext,
        pack_name: str,
        source: str = "llm",
        allowed_rule_ids: set[str] | None = None,
    ) -> tuple[list[Issue], list[str]]:
        """Convert a critic response to issues.

        When allowed_rule_ids is given, findings citing any other rule are
        dropped - the analyzer was explicitly told not to invent rules.
        Findings pointing outside the file's line range are dropped too.

        Returns:
            Tuple of (issues, warnings). Warnings describe entries that were
            dropped and why, so they can be logged or shown to the agent.
        """
        issues: list[Issue] = []
        warnings: list[str] = []
        total_lines = file_ctx.content.count("\n") + 1

        for critic_issue in response.issues:
            location = f"{file_ctx.path}:{critic_issue.location.start_line}"

            if allowed_rule_ids is not None and critic_issue.rule_id not in allowed_rule_ids:
                warnings.append(
                    f"{location}: rule '{critic_issue.rule_id}' is not in this file's "
                    f"rule list - issue dropped"
                )
                continue

            try:
                level = IssueLevel(critic_issue.level)
            except ValueError:
                warnings.append(
                    f"{location}: invalid level '{critic_issue.level}' "
                    f"(expected one of {', '.join(SEVERITY_ORDER)}) - issue dropped"
                )
                continue

            start_line = critic_issue.location.start_line
            end_line = critic_issue.location.end_line
            if start_line < 1 or start_line > total_lines:
                warnings.append(
                    f"{location}: start_line out of range (file has {total_lines} lines) "
                    f"- issue dropped"
                )
                continue
            if end_line is not None:
                # A slightly overshot end is a common off-by-one; clamp it
                end_line = max(start_line, min(end_line, total_lines))

            try:
                snippet = CodeExtractor.extract_snippet(file_ctx.content, start_line, end_line)
                context = CodeExtractor.extract_context(file_ctx.content, start_line)

                issues.append(
                    Issue(
                        rule_id=critic_issue.rule_id,
                        level=level,
                        location=Location(
                            path=file_ctx.path,
                            start_line=start_line,
                            end_line=end_line,
                        ),
                        title=critic_issue.title,
                        why=critic_issue.why,
                        do=critic_issue.do,
                        pack=pack_name,
                        source=source,
                        confidence=critic_issue.confidence,
                        tags=critic_issue.tags,
                        snippet=snippet,
                        context=context,
                    )
                )
            except Exception as e:
                warnings.append(f"{location}: could not build issue ({e}) - issue dropped")

        return issues, warnings

    def filter_rules(self, issues: list[Issue], rule_filter: list[str] | None) -> list[Issue]:
        """Keep only issues whose rule_id matches any of the given filters."""
        if not rule_filter:
            return issues
        return [issue for issue in issues if any(f in issue.rule_id for f in rule_filter)]

    def filter_disabled(self, issues: list[Issue], disabled_rules: list[str]) -> list[Issue]:
        """Remove issues from disabled rules."""
        if not disabled_rules:
            return issues
        return [issue for issue in issues if issue.rule_id not in disabled_rules]

    def deduplicate(self, issues: list[Issue]) -> list[Issue]:
        """Remove duplicate issues by issue_id."""
        seen = set()
        unique = []
        for issue in issues:
            if issue.issue_id not in seen:
                seen.add(issue.issue_id)
                unique.append(issue)
        return unique

    def limit_per_file(self, issues: list[Issue]) -> list[Issue]:
        """Keep the most severe MAX_ISSUES_PER_FILE issues per file."""
        by_file: dict[str, list[Issue]] = {}
        for issue in issues:
            path = str(issue.location.path)
            if path not in by_file:
                by_file[path] = []
            by_file[path].append(issue)

        limited = []
        for file_issues in by_file.values():
            file_issues.sort(key=lambda i: SEVERITY_ORDER.index(i.level.value))
            limited.extend(file_issues[:MAX_ISSUES_PER_FILE])

        return limited

    def finalize(
        self,
        issues: list[Issue],
        rule_filter: list[str] | None = None,
        disabled_rules: list[str] | None = None,
    ) -> list[Issue]:
        """Apply the full post-processing pipeline: filters, dedupe, per-file limit."""
        issues = self.filter_rules(issues, rule_filter)
        issues = self.filter_disabled(issues, disabled_rules or [])
        issues = self.deduplicate(issues)
        return self.limit_per_file(issues)
