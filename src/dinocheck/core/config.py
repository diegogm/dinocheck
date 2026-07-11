"""Configuration loading and management for Dinocheck."""

from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default cache location
DEFAULT_CACHE_DB = ".dinocheck/cache.db"

# Analyzer identity used for cache keys and run logs
AGENT_ANALYZER = "agent"


class DinocheckConfig(BaseModel):
    """Main Dinocheck configuration.

    Dinocheck is agent-native: the host coding agent performs the analysis
    via `dino brief` / `dino report`, so no LLM provider, model, or API key
    is ever configured.
    """

    packs: list[str] | None = None  # None = all packs enabled
    exclude_packs: list[str] = Field(default_factory=list)
    language: str = "en"
    disabled_rules: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)
    include_paths: list[str] | None = None  # None = current directory


class EnvSettings(BaseSettings):
    """Environment-based settings (from .env or environment)."""

    model_config = SettingsConfigDict(
        env_prefix="DINO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    language: str | None = None


class ConfigManager:
    """Manages configuration loading, validation, and access."""

    def __init__(self, config_path: Path | None = None):
        self._config_path = config_path
        self._config: DinocheckConfig | None = None

    @staticmethod
    def find_config_file(start_path: Path | None = None) -> Path | None:
        """Find dino.yaml in current or parent directories."""
        if start_path is None:
            start_path = Path.cwd()

        current = start_path.resolve()
        while True:
            config_path = current / "dino.yaml"
            if config_path.exists():
                return config_path
            parent = current.parent
            if parent == current:  # Reached root
                break
            current = parent

        return None

    def load(self) -> DinocheckConfig:
        """Load configuration from dino.yaml and .env files.

        Priority (highest to lowest):
        1. Environment variables (DINO_LANGUAGE)
        2. .env file (in same directory as dino.yaml)
        3. dino.yaml
        4. Defaults
        """
        # Find config file first
        config_path = self._config_path or self.find_config_file()

        # Error if explicit config path was provided but doesn't exist
        if self._config_path and not self._config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self._config_path}")

        # Load .env from same directory as config file (or cwd if no config)
        env_path = config_path.parent / ".env" if config_path else Path.cwd() / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        # Load environment settings
        env_settings = EnvSettings()

        config_dict: dict[str, object] = {}
        if config_path and config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                raw = yaml.safe_load(f)
                if raw:
                    config_dict = raw

        # Create config (unknown keys, e.g. legacy settings, are ignored)
        self._config = DinocheckConfig.model_validate(config_dict)

        # Override with environment settings
        if env_settings.language:
            self._config.language = env_settings.language

        return self._config

    @property
    def config(self) -> DinocheckConfig:
        """Get loaded config, loading if necessary."""
        if self._config is None:
            self.load()
        assert self._config is not None
        return self._config

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        # Check packs - None means all packs, which is valid
        # Only error if explicitly set to empty list
        if self.config.packs is not None and len(self.config.packs) == 0:
            errors.append("No packs configured (use packs: null for all packs)")

        return errors
