"""JSON formatter for programmatic consumption."""

import json

from dinocrit.core.interfaces import Formatter
from dinocrit.core.types import AnalysisResult


class JSONFormatter(Formatter):
    """JSON output for programmatic consumption."""

    @property
    def name(self) -> str:
        return "json"

    def format(self, result: AnalysisResult) -> str:
        return json.dumps(result.to_dict(), indent=2)
