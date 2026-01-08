"""Configuration loading and management for Dinocheck."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default cache location
DEFAULT_CACHE_DB = ".dinocheck/cache.db"


class DinocheckConfig(BaseModel):
    """Main Dinocheck configuration - simplified."""

    packs: list[str] = Field(default_factory=lambda: ["python"])
    model: str = "openai/gpt-5.1-codex"
    language: str = "en"
    max_llm_calls: int = 10
    disabled_rules: list[str] = Field(default_factory=list)

    @property
    def provider(self) -> str:
        """Extract provider from model string."""
        if "/" in self.model:
            return self.model.split("/")[0]
        return "openai"

    @property
    def model_name(self) -> str:
        """Extract model name from model string."""
        if "/" in self.model:
            return self.model.split("/", 1)[1]
        return self.model

    @property
    def api_key_env(self) -> str:
        """Infer API key environment variable from provider."""
        provider_keys = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "azure": "AZURE_API_KEY",
            "ollama": "",  # Ollama doesn't need API key
        }
        return provider_keys.get(self.provider, "OPENAI_API_KEY")


class EnvSettings(BaseSettings):
    """Environment-based settings (from .env or environment)."""

    model_config = SettingsConfigDict(
        env_prefix="DINO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str | None = None
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
        1. Environment variables (DINO_*)
        2. .env file (in same directory as dino.yaml)
        3. dino.yaml
        4. Defaults
        """
        # Find config file first
        config_path = self._config_path or self.find_config_file()

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

        # Create config
        self._config = DinocheckConfig.model_validate(config_dict)

        # Override with environment settings
        if env_settings.model:
            self._config.model = env_settings.model
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

    def get_api_key(self) -> str | None:
        """Get API key from environment based on config."""
        if not self.config.api_key_env:
            return "not-needed"  # For local providers like Ollama
        return os.environ.get(self.config.api_key_env)

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        # Check API key (skip for local providers)
        if self.config.provider not in ("ollama",):
            api_key = self.get_api_key()
            if not api_key:
                errors.append(f"API key not found: {self.config.api_key_env}")

        # Check packs
        if not self.config.packs:
            errors.append("No packs configured")

        # Check budget
        if self.config.max_llm_calls < 0:
            errors.append("max_llm_calls must be >= 0")

        return errors
