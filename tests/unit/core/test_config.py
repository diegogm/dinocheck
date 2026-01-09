"""Tests for configuration loading."""

import pytest

from dinocheck.core.config import ConfigManager, DinocheckConfig


class TestDinocheckConfig:
    """Tests for DinocheckConfig."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = DinocheckConfig()
        assert config.packs is None  # None means all packs enabled
        assert config.language == "en"
        assert config.max_llm_calls >= 1

    def test_custom_model(self):
        """Should accept custom model."""
        config = DinocheckConfig(model="anthropic/claude-3-5-sonnet")
        assert config.model == "anthropic/claude-3-5-sonnet"
        assert config.provider == "anthropic"
        assert config.model_name == "claude-3-5-sonnet"

    def test_provider_extraction(self):
        """Should extract provider from model string."""
        config = DinocheckConfig(model="openai/gpt-4o")
        assert config.provider == "openai"
        assert config.model_name == "gpt-4o"

    def test_api_key_env_inference(self):
        """Should infer API key env from provider."""
        openai = DinocheckConfig(model="openai/gpt-4o")
        assert openai.api_key_env == "OPENAI_API_KEY"

        anthropic = DinocheckConfig(model="anthropic/claude-3")
        assert anthropic.api_key_env == "ANTHROPIC_API_KEY"

    def test_multiple_packs(self):
        """Should accept multiple packs."""
        config = DinocheckConfig(packs=["python", "django"])
        assert "python" in config.packs
        assert "django" in config.packs

    def test_disabled_rules(self):
        """Should accept disabled rules."""
        config = DinocheckConfig(disabled_rules=["python/foo", "django/bar"])
        assert "python/foo" in config.disabled_rules


class TestConfigManager:
    """Tests for ConfigManager."""

    def test_load_from_yaml(self, tmp_path, monkeypatch):
        """Should load config from YAML file."""
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "dino.yaml"
        config_file.write_text("""
packs:
  - python
  - django
model: openai/gpt-4o
language: es
""")

        manager = ConfigManager(config_file)
        config = manager.load()

        assert "python" in config.packs
        assert "django" in config.packs
        assert config.model == "openai/gpt-4o"
        assert config.language == "es"

    def test_load_nonexistent_file(self, tmp_path, monkeypatch):
        """Should return defaults for missing file."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "nonexistent.yaml"

        manager = ConfigManager(config_file)

        # Should raise error when explicit config path doesn't exist
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            manager.load()

    def test_load_with_env_override(self, tmp_path, monkeypatch):
        """Should override with environment variables."""
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "dino.yaml"
        config_file.write_text("""
packs:
  - python
model: openai/gpt-4o-mini
""")

        # Set environment override
        monkeypatch.setenv("DINO_MODEL", "anthropic/claude-3-5-sonnet")
        monkeypatch.setenv("DINO_LANGUAGE", "fr")

        manager = ConfigManager(config_file)
        config = manager.load()

        # Environment should override YAML
        assert config.model == "anthropic/claude-3-5-sonnet"
        assert config.language == "fr"

    def test_load_with_dotenv(self, tmp_path, monkeypatch):
        """Should load from .env file."""
        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("""
OPENAI_API_KEY=sk-test-key
DINO_MODEL=openai/gpt-4o
""")

        # Change to tmp_path so .env is found
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "dino.yaml"
        config_file.write_text("""
packs:
  - python
""")

        manager = ConfigManager(config_file)
        config = manager.load()

        assert config.model == "openai/gpt-4o"

    def test_validate_missing_api_key(self, tmp_path, monkeypatch):
        """Should report error for missing API key."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        manager = ConfigManager()
        manager.load()
        errors = manager.validate()

        assert any("API key" in e for e in errors)

    def test_validate_no_packs(self):
        """Should report error for no packs."""
        manager = ConfigManager()
        manager._config = DinocheckConfig(packs=[])
        errors = manager.validate()

        assert any("packs" in e.lower() for e in errors)

    def test_get_api_key(self, monkeypatch):
        """Should get API key from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")

        manager = ConfigManager()
        manager._config = DinocheckConfig(model="openai/gpt-4o")

        assert manager.get_api_key() == "sk-test-123"
