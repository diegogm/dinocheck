"""Builder for agent-mode review briefs.

A brief is the instruction document `dino brief` hands to the host coding
agent: which files to review, which rules apply to each (full text, with
checklists and examples), and the exact output contract for `dino report`.
Files are referenced by path - the host agent reads them with its own
tools - unless embed_code is requested.
"""

import json
from typing import Any

from dinocheck.core.config import DinocheckConfig
from dinocheck.core.types import AnalysisPlan, FileAnalysisTask, Rule
from dinocheck.utils.languages import LanguageDetector


class BriefBuilder:
    """Builds review briefs from an analysis plan."""

    HEADER_TEMPLATE = """# Dinocheck Review Brief

You are performing a Dinocheck code review. Dinocheck is a vibe coding
companion - it provides a second opinion on code, it does not fix it.

## Instructions

1. For each file listed below, read the file and evaluate ONLY the rules
   listed for it, using their checklists. Do not invent new rules.
2. Only report issues you are confident about (>= 80% confidence).
3. Be specific: identify exact line numbers and provide actionable suggestions.
4. Prioritize security and correctness over style.
5. A file with no issues gets an empty issues array.
{language_instruction}
## Output contract

Write a single JSON file with this exact shape:

```json
{{
  "files": [
    {{
      "path": "<path exactly as listed below>",
      "issues": [
        {{
          "rule_id": "<rule ID from the file's rule list>",
          "level": "blocker|critical|major|minor|info",
          "location": {{"start_line": <int>, "end_line": <int>}},
          "title": "<brief issue title, max 80 chars>",
          "why": "<why this is an issue, 1-2 sentences>",
          "do": ["<specific action item to fix>", "..."],
          "confidence": <0.0-1.0>,
          "tags": []
        }}
      ]
    }}
  ]
}}
```

Include one entry per file listed below, even when its issues array is empty.
When done, submit the results with:

```bash
dino report <results-file.json>
```
"""

    @classmethod
    def build_markdown(
        cls,
        plan: AnalysisPlan,
        config: DinocheckConfig,
        embed_code: bool = False,
    ) -> str:
        """Build a Markdown review brief for the host agent."""
        sections = [cls._build_header(config)]

        if not plan.tasks:
            sections.append(cls._build_empty_notice(plan))
            return "\n".join(sections)

        sections.append(f"## Files to review ({len(plan.tasks)})\n")
        for task in plan.tasks:
            sections.append(cls._build_file_section(task, embed_code))

        sections.append(cls._build_footer(plan))
        return "\n".join(sections)

    @classmethod
    def build_json(
        cls,
        plan: AnalysisPlan,
        config: DinocheckConfig,
        embed_code: bool = False,
    ) -> str:
        """Build a JSON review brief for programmatic consumption."""
        data: dict[str, Any] = {
            "instructions": cls._build_header(config),
            "files": [
                {
                    "path": str(task.file_ctx.path),
                    "lines": task.file_ctx.content.count("\n") + 1,
                    "rules": [cls._rule_to_dict(rule) for rule in task.rules],
                    **({"content": task.file_ctx.content} if embed_code else {}),
                }
                for task in plan.tasks
            ],
            "summary": {
                "files_total": plan.files_total,
                "files_to_review": len(plan.tasks),
                "cache_hits": plan.cache_hits,
                "cached_issues": len(plan.cached_issues),
                "skipped_no_rules": plan.skipped_no_rules,
            },
            "report_command": "dino report <results-file.json>",
        }
        return json.dumps(data, indent=2)

    @classmethod
    def _build_header(cls, config: DinocheckConfig) -> str:
        language_instruction = ""
        if config.language != "en":
            language_instruction = (
                f"6. Respond in {config.language}: all issue titles, explanations, "
                f"and action items must be in {config.language}.\n"
            )
        return cls.HEADER_TEMPLATE.format(language_instruction=language_instruction)

    @classmethod
    def _build_empty_notice(cls, plan: AnalysisPlan) -> str:
        return (
            "## Nothing to analyze\n\n"
            f"All {plan.files_total} discovered file(s) are already covered: "
            f"{plan.cache_hits} cached, {plan.skipped_no_rules} with no applicable rules.\n"
            "Tell the user everything is up to date - do not run `dino report`.\n"
        )

    @classmethod
    def _build_file_section(cls, task: FileAnalysisTask, embed_code: bool) -> str:
        file_ctx = task.file_ctx
        lines = file_ctx.content.count("\n") + 1
        parts = [f"### {file_ctx.path} ({lines} lines)\n"]

        parts.append(f"Rules to evaluate ({len(task.rules)}):\n")
        for rule in task.rules:
            parts.append(cls._format_rule(rule, file_ctx.path.suffix))

        if embed_code:
            fence = LanguageDetector.fence_language(file_ctx.path)
            parts.append(f"File content:\n\n```{fence}\n{file_ctx.content}\n```\n")

        return "\n".join(parts)

    @classmethod
    def _format_rule(cls, rule: Rule, file_suffix: str) -> str:
        parts = [f"#### {rule.id} — {rule.name} [{rule.level.value}]\n"]
        if rule.description.strip():
            parts.append(f"{rule.description.strip()}\n")
        if rule.checklist:
            parts.append("Checklist:")
            parts.extend(f"- {item}" for item in rule.checklist)
            parts.append("")
        if rule.fix.strip():
            parts.append(f"Fix guidance: {rule.fix.strip()}\n")
        if rule.examples:
            fence = LanguageDetector.EXTENSION_LANGUAGES.get(file_suffix.lower(), "text")
            if "bad" in rule.examples:
                parts.append(f"Bad example:\n\n```{fence}\n{rule.examples['bad'].rstrip()}\n```\n")
            if "good" in rule.examples:
                parts.append(
                    f"Good example:\n\n```{fence}\n{rule.examples['good'].rstrip()}\n```\n"
                )
        return "\n".join(parts)

    @classmethod
    def _build_footer(cls, plan: AnalysisPlan) -> str:
        parts = ["## Coverage notes\n"]
        parts.append(f"- {plan.files_total} file(s) discovered, {len(plan.tasks)} pending review.")
        if plan.cache_hits:
            parts.append(
                f"- {plan.cache_hits} file(s) already analyzed and cached "
                f"({len(plan.cached_issues)} known issue(s)); do not re-review them."
            )
        if plan.skipped_no_rules:
            parts.append(f"- {plan.skipped_no_rules} file(s) skipped: no applicable rules.")
        parts.append("")
        return "\n".join(parts)

    @classmethod
    def _rule_to_dict(cls, rule: Rule) -> dict[str, Any]:
        return {
            "id": rule.id,
            "name": rule.name,
            "level": rule.level.value,
            "category": rule.category,
            "description": rule.description,
            "checklist": rule.checklist,
            "fix": rule.fix,
            "examples": rule.examples or {},
            "tags": rule.tags,
        }
