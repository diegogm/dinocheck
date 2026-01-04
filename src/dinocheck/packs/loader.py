"""Pack loading and discovery.

Supports:
- Built-in packs (python, django)
- Custom YAML rules from .dinocheck/rules/ directory
"""

from collections.abc import Iterator
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from dinocheck.core.interfaces import Pack
from dinocheck.core.types import Rule

_pack_registry: dict[str, Pack] = {}
_custom_rules_loaded = False


def register_pack(pack: Pack) -> None:
    """Register a pack in the global registry."""
    _pack_registry[pack.name] = pack


def get_pack(name: str) -> Pack:
    """Get a pack by name."""
    # Lazy load built-in packs
    _ensure_builtin_packs()

    if name not in _pack_registry:
        raise ValueError(f"Pack not found: {name}")

    return _pack_registry[name]


def get_all_packs() -> Iterator[Pack]:
    """Get all registered packs."""
    _ensure_builtin_packs()
    yield from _pack_registry.values()


def get_packs(names: list[str]) -> list[Pack]:
    """Get multiple packs by name."""
    return [get_pack(name) for name in names]


def _ensure_builtin_packs() -> None:
    """Ensure built-in packs are loaded."""
    if "python" not in _pack_registry:
        from dinocheck.packs.python.pack import PythonPack

        register_pack(PythonPack())

    if "django" not in _pack_registry:
        from dinocheck.packs.django.pack import DjangoPack

        register_pack(DjangoPack())


def load_rules_from_directory(rules_dir: Path) -> list[Rule]:
    """Load rules from YAML files in a directory.

    Args:
        rules_dir: Directory containing .yaml rule files.

    Returns:
        List of Rule objects loaded from YAML files.
    """
    rules: list[Rule] = []

    if not rules_dir.exists():
        return rules

    for yaml_file in rules_dir.glob("**/*.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict) and "id" in data:
                    rule = Rule.from_yaml(data)
                    rules.append(rule)
        except Exception as e:
            import logging

            logging.warning(f"Failed to load rule from {yaml_file}: {e}")

    return rules


def load_custom_rules(rules_dir: Path | str | None = None) -> list[Rule]:
    """Load custom rules from YAML files.

    Args:
        rules_dir: Directory containing .yaml rule files.
                   Defaults to .dinocheck/rules/ in current directory.

    Returns:
        List of Rule objects loaded from YAML files.

    Custom rules should be YAML files with the following structure:

    ```yaml
    id: my-pack/my-rule
    name: My Custom Rule
    level: major  # blocker, critical, major, minor, info
    category: security
    description: |
      Description of what this rule checks.
    checklist:
      - First thing to check
      - Second thing to check
    fix: How to fix the issue.
    tags:
      - security
      - custom
    triggers:
      file_patterns:
        - "**/views.py"
      code_patterns:
        - "dangerous_function\\("
    examples:
      bad: |
        # Bad example
        dangerous_function(user_input)
      good: |
        # Good example
        safe_function(sanitize(user_input))
    ```
    """
    rules_path = Path.cwd() / ".dinocheck" / "rules" if rules_dir is None else Path(rules_dir)
    return load_rules_from_directory(rules_path)


class CustomRulesPack(Pack):
    """Pack containing custom YAML rules."""

    def __init__(self, rules_dir: Path | str | None = None):
        self._rules = load_custom_rules(rules_dir)

    @property
    def name(self) -> str:
        return "custom"

    @property
    def version(self) -> str:
        return "local"

    @property
    def rules(self) -> list[Rule]:
        return self._rules


class PackCompositor:
    """Composes multiple packs with proper precedence."""

    def compose(self, pack_names: list[str], overlays: list[Pack] | None = None) -> "ComposedPack":
        """
        Compose packs with proper precedence.

        Composition order (later overrides earlier):
        1. Language pack (base rules)
        2. Framework pack (extends/overrides)
        3. Team/repo overlays (final overrides)
        """
        packs = get_packs(pack_names)
        overlays = overlays or []

        all_rules: dict[str, Rule] = {}

        # Add rules from each pack
        for pack in packs + overlays:
            for rule in pack.rules:
                all_rules[rule.id] = rule

        return ComposedPack(
            name="+".join(pack_names),
            version="composed",
            rules_dict=all_rules,
        )


class ComposedPack(Pack):
    """A pack composed from multiple source packs."""

    def __init__(
        self,
        name: str,
        version: str,
        rules_dict: dict[str, Rule],
    ) -> None:
        self._name = name
        self._version = version
        self._rules_dict = rules_dict

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules_dict.values())
