"""Output formatters for Dinocheck."""

from dinocheck.cli.formatters.json_formatter import JSONFormatter
from dinocheck.cli.formatters.jsonl_formatter import JSONLFormatter
from dinocheck.cli.formatters.text_formatter import TextFormatter
from dinocheck.core.interfaces import Formatter

_formatters: dict[str, Formatter] = {
    "text": TextFormatter(),
    "json": JSONFormatter(),
    "jsonl": JSONLFormatter(),
}


def get_formatter(name: str) -> Formatter:
    """Get formatter by name."""
    if name not in _formatters:
        raise ValueError(f"Unknown formatter: {name}")
    return _formatters[name]


__all__ = [
    "Formatter",
    "JSONFormatter",
    "JSONLFormatter",
    "TextFormatter",
    "get_formatter",
]
