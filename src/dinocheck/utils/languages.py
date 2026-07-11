"""Language detection for code fences in prompts and briefs."""

from pathlib import Path
from typing import ClassVar


class LanguageDetector:
    """Maps file extensions to Markdown code-fence language identifiers."""

    EXTENSION_LANGUAGES: ClassVar[dict[str, str]] = {
        ".py": "python",
        ".pyi": "python",
        ".js": "javascript",
        ".jsx": "jsx",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".vue": "vue",
        ".tex": "latex",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".md": "markdown",
        ".sh": "bash",
        ".sql": "sql",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
    }

    @classmethod
    def fence_language(cls, path: Path) -> str:
        """Return the fence language for a file path ('text' when unknown)."""
        return cls.EXTENSION_LANGUAGES.get(path.suffix.lower(), "text")
