"""Pack loading and discovery.

Packs are automatically discovered from subdirectories in the packs/ folder.
Each pack is a directory containing:
- rules/: Directory with YAML rule files
- pack.yaml (optional): Pack metadata (name, version, description)

Custom rules can also be loaded from .dinocheck/rules/ in the project directory.
"""

from collections.abc import Iterator
from pathlib import Path

import yaml

from dinocheck.core.interfaces import Pack
from dinocheck.core.types import Rule

_pack_registry: dict[str, Pack] = {}
_builtin_packs_loaded = False


class DirectoryPack(Pack):
    """A pack loaded from a directory structure."""

    def __init__(self, pack_dir: Path) -> None:
        self._pack_dir = pack_dir
        self._name = pack_dir.name
        self._version = "0.1.0"
        self._description = ""

        # Load metadata from pack.yaml if exists
        metadata_file = pack_dir / "pack.yaml"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = yaml.safe_load(f) or {}
                self._name = metadata.get("name", self._name)
                self._version = metadata.get("version", self._version)
                self._description = metadata.get("description", self._description)

        # Load rules from rules/ directory
        rules_dir = pack_dir / "rules"
        self._rules = load_rules_from_directory(rules_dir)

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def description(self) -> str:
        return self._description

    @property
    def rules(self) -> list[Rule]:
        return self._rules


def register_pack(pack: Pack) -> None:
    """Register a pack in the global registry."""
    _pack_registry[pack.name] = pack


def get_pack(name: str) -> Pack:
    """Get a pack by name."""
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


def _discover_builtin_packs() -> list[Pack]:
    """Discover all built-in packs from the packs directory."""
    packs_dir = Path(__file__).parent
    discovered: list[Pack] = []

    for item in packs_dir.iterdir():
        # Skip non-directories and special directories
        if not item.is_dir():
            continue
        if item.name.startswith("_") or item.name.startswith("."):
            continue
        if item.name == "__pycache__":
            continue

        # Check if it has a rules/ directory
        rules_dir = item / "rules"
        if rules_dir.exists() and rules_dir.is_dir():
            pack = DirectoryPack(item)
            if pack.rules:  # Only add if it has rules
                discovered.append(pack)

    return discovered


def _ensure_builtin_packs() -> None:
    """Ensure built-in packs are loaded."""
    global _builtin_packs_loaded

    if _builtin_packs_loaded:
        return

    for pack in _discover_builtin_packs():
        if pack.name not in _pack_registry:
            register_pack(pack)

    _builtin_packs_loaded = True


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
