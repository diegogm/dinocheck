"""JSON Lines formatter for streaming output."""

import json

from dinocheck.core.interfaces import Formatter
from dinocheck.core.types import AnalysisResult


class JSONLFormatter(Formatter):
    """JSON Lines output for streaming."""

    @property
    def name(self) -> str:
        return "jsonl"

    def format(self, result: AnalysisResult) -> str:
        lines = []
        # Summary line
        lines.append(
            json.dumps(
                {
                    "type": "summary",
                    "score": result.score,
                    "issues_count": len(result.issues),
                }
            )
        )
        # Issue lines
        for issue in result.issues:
            lines.append(json.dumps({"type": "issue", **issue.to_dict()}))
        return "\n".join(lines)
