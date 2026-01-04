"""Prompt builder for code critic analysis."""

from dinocheck.core.types import FileContext, Rule


class CriticPromptBuilder:
    """Builds prompts for LLM code analysis.

    Separates prompt construction from engine logic for better
    maintainability and testability.
    """

    MAX_CONTENT_LENGTH = 10000

    SYSTEM_TEMPLATE = """You are Dinocheck, an expert code reviewer specializing in {pack_name}.
Your task is to identify code quality issues based on the provided rules and context.

Dinocheck is a vibe coding companion - it helps developers by providing a second opinion
on their code, not by fixing it for them. Focus on identifying issues and explaining them clearly.

IMPORTANT GUIDELINES:
1. Only flag issues you are confident about (≥80% confidence)
2. Be specific: identify exact line numbers and provide actionable suggestions
3. Focus on the rules provided - do not invent new rules
4. Prioritize security and correctness over style
5. Return an empty issues array if no issues are found

OUTPUT FORMAT:
Return a JSON object with:
- issues: Array of issues found

Each issue must have:
- rule_id: The rule ID from the provided rules
- level: blocker|critical|major|minor|info
- location: {{start_line, end_line}}
- title: Brief issue title (max 80 chars)
- why: Explanation of why this is an issue (1-2 sentences)
- do: Array of specific action items to fix (1-3 items)
- confidence: 0.0-1.0
"""

    USER_TEMPLATE = """{language_instruction}
## File: {file_path}

## Active Rules:
{rules_text}

## Code to Review:
```python
{content}
```

Analyze the code for issues matching the active rules. Focus on the most critical issues first.
Return your findings as JSON with the schema provided.
"""

    @classmethod
    def build_system_prompt(cls, pack_name: str) -> str:
        """Build system prompt for LLM."""
        return cls.SYSTEM_TEMPLATE.format(pack_name=pack_name)

    @classmethod
    def build_user_prompt(
        cls,
        file_ctx: FileContext,
        rules: list[Rule],
        language: str = "en",
    ) -> str:
        """Build user prompt for LLM analysis."""
        rules_text = cls._format_rules(rules)
        content = file_ctx.content[: cls.MAX_CONTENT_LENGTH]
        language_instruction = cls._get_language_instruction(language)

        return cls.USER_TEMPLATE.format(
            language_instruction=language_instruction,
            file_path=file_ctx.path,
            rules_text=rules_text,
            content=content,
        )

    @classmethod
    def _format_rules(cls, rules: list[Rule]) -> str:
        """Format rules list for prompt."""
        return "\n".join(
            [f"- {r.id}: {r.name} ({r.level.value}) - {r.description[:100]}..." for r in rules]
        )

    @classmethod
    def _get_language_instruction(cls, language: str) -> str:
        """Get language instruction if not English."""
        if language == "en":
            return ""
        return (
            f"\nIMPORTANT: Respond in {language}. "
            f"All issue titles, explanations, and action items must be in {language}.\n"
        )
