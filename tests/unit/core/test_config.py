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
        assert config.exclude_packs == []
        assert config.disabled_rules == []

    def test_multiple_packs(self):
        """Should accept multiple packs."""
        config = DinocheckConfig(packs=["python", "django"])
        assert "python" in config.packs
        assert "django" in config.packs

    def test_disabled_rules(self):
        """Should accept disabled rules."""
        config = DinocheckConfig(disabled_rules=["python/foo", "django/bar"])
        assert "python/foo" in config.disabled_rules


class TestPathFiltering:
    """Tests for exclude_paths and include_paths config fields."""

    def test_exclude_paths_default_empty(self):
        """Should default to empty list."""
        config = DinocheckConfig()
        assert config.exclude_paths == []

    def test_include_paths_default_none(self):
        """Should default to None."""
        config = DinocheckConfig()
        assert config.include_paths is None

    def test_exclude_paths_from_yaml(self, tmp_path, monkeypatch):
        """Should load exclude_paths from YAML."""
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "dino.yaml"
        config_file.write_text("""
exclude_paths:
  - migrations
  - tests/fixtures
""")

        manager = ConfigManager(config_file)
        config = manager.load()

        assert "migrations" in config.exclude_paths
        assert "tests/fixtures" in config.exclude_paths

    def test_include_paths_from_yaml(self, tmp_path, monkeypatch):
        """Should load include_paths from YAML."""
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "dino.yaml"
        config_file.write_text("""
include_paths:
  - src/
  - lib/
""")

        manager = ConfigManager(config_file)
        config = manager.load()

        assert "src/" in config.include_paths
        assert "lib/" in config.include_paths


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
language: es
""")

        manager = ConfigManager(config_file)
        config = manager.load()

        assert "python" in config.packs
        assert "django" in config.packs
        assert config.language == "es"

    def test_load_ignores_legacy_api_settings(self, tmp_path, monkeypatch):
        """A dino.yaml with removed api-mode keys must still load."""
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "dino.yaml"
        config_file.write_text("""
packs:
  - python
mode: api
model: openai/gpt-4o
max_llm_calls: 10
""")

        manager = ConfigManager(config_file)
        config = manager.load()

        assert config.packs == ["python"]
        assert not hasattr(config, "model")

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
language: en
""")

        # Set environment override
        monkeypatch.setenv("DINO_LANGUAGE", "fr")

        manager = ConfigManager(config_file)
        config = manager.load()

        # Environment should override YAML
        assert config.language == "fr"

    def test_load_with_dotenv(self, tmp_path, monkeypatch):
        """Should load from .env file."""
        monkeypatch.delenv("DINO_LANGUAGE", raising=False)

        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("""
DINO_LANGUAGE=es
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

        assert config.language == "es"

    def test_validate_default_config_is_clean(self, tmp_path, monkeypatch):
        """The default (empty) configuration must validate with no errors."""
        monkeypatch.chdir(tmp_path)

        manager = ConfigManager()
        manager.load()
        errors = manager.validate()

        assert errors == []

    def test_validate_no_packs(self):
        """Should report error for no packs."""
        manager = ConfigManager()
        manager._config = DinocheckConfig(packs=[])
        errors = manager.validate()

        assert any("packs" in e.lower() for e in errors)
