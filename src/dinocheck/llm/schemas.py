"""Pydantic schemas for LLM structured outputs."""

from pydantic import BaseModel, Field


class IssueLocation(BaseModel):
    """Location of an issue in source code."""

    start_line: int
    end_line: int | None = None


class CriticIssue(BaseModel):
    """Structured output for a single issue from LLM."""

    rule_id: str = Field(description="Rule ID from provided rules, e.g., 'django/n-plus-one'")
    level: str = Field(description="blocker|critical|major|minor|info")
    location: IssueLocation
    title: str = Field(max_length=80, description="Brief issue title")
    why: str = Field(description="Explanation of why this is an issue (1-2 sentences)")
    do: list[str] = Field(description="Specific action items to fix (1-3 items)")
    confidence: float = Field(ge=0.0, le=1.0, default=0.9)
    tags: list[str] = Field(default_factory=list)


class CriticResponse(BaseModel):
    """Structured output for LLM critic analysis."""

    issues: list[CriticIssue] = Field(default_factory=list)
