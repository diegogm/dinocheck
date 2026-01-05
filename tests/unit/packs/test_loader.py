"""Tests for pack loading and composition."""

import pytest

from dinocheck.core.types import IssueLevel
from dinocheck.packs.loader import get_all_packs, get_pack, get_packs, load_custom_rules


class TestPackLoader:
    """Tests for pack loading functions."""

    def test_get_python_pack(self):
        """Should get Python pack."""
        pack = get_pack("python")

        assert pack is not None
        assert pack.name == "python"
        assert len(pack.rules) > 0

    def test_get_django_pack(self):
        """Should get Django pack."""
        pack = get_pack("django")

        assert pack is not None
        assert pack.name == "django"
        assert len(pack.rules) > 0

    def test_get_unknown_pack(self):
        """Should raise error for unknown pack."""
        with pytest.raises(ValueError):
            get_pack("unknown-pack")

    def test_get_multiple_packs(self):
        """Should get multiple packs."""
        packs = get_packs(["python", "django"])

        assert len(packs) == 2
        assert any(p.name == "python" for p in packs)
        assert any(p.name == "django" for p in packs)

    def test_get_all_packs(self):
        """Should get all registered packs."""
        packs = list(get_all_packs())

        assert len(packs) >= 2
        assert any(p.name == "python" for p in packs)
        assert any(p.name == "django" for p in packs)


class TestPythonPack:
    """Tests for Python pack."""

    @pytest.fixture
    def pack(self):
        """Get Python pack."""
        return get_pack("python")

    def test_pack_name(self, pack):
        """Should have correct name."""
        assert pack.name == "python"

    def test_pack_version(self, pack):
        """Should have version."""
        assert pack.version is not None
        assert len(pack.version) > 0

    def test_has_rules(self, pack):
        """Should have rules defined."""
        assert len(pack.rules) >= 5

    def test_rules_have_required_fields(self, pack):
        """Rules should have required fields."""
        for rule in pack.rules:
            assert rule.id.startswith("python/")
            assert rule.name
            assert rule.level in IssueLevel
            assert rule.checklist

    def test_has_semantic_rules(self, pack):
        """Should have semantic analysis rules."""
        rule_ids = [r.id for r in pack.rules]
        # These rules require semantic LLM analysis, not pattern matching
        assert "python/error-handling" in rule_ids
        assert "python/business-logic" in rule_ids


class TestDjangoPack:
    """Tests for Django pack."""

    @pytest.fixture
    def pack(self):
        """Get Django pack."""
        return get_pack("django")

    def test_pack_name(self, pack):
        """Should have correct name."""
        assert pack.name == "django"

    def test_pack_version(self, pack):
        """Should have version."""
        assert pack.version is not None

    def test_has_rules(self, pack):
        """Should have rules defined."""
        assert len(pack.rules) >= 10

    def test_has_n_plus_one_rule(self, pack):
        """Should have N+1 query rule."""
        rule_ids = [r.id for r in pack.rules]
        assert "django/n-plus-one" in rule_ids

    def test_has_api_authorization_rule(self, pack):
        """Should have API authorization rule."""
        rule_ids = [r.id for r in pack.rules]
        assert "django/api-authorization" in rule_ids

    def test_critical_rules_exist(self, pack):
        """Should have critical-level rules."""
        criticals = [r for r in pack.rules if r.level == IssueLevel.CRITICAL]
        assert len(criticals) > 0

    def test_rules_have_examples(self, pack):
        """Some rules should have examples."""
        rules_with_examples = [r for r in pack.rules if r.examples]
        assert len(rules_with_examples) > 0

    def test_drf_rules_exist(self, pack):
        """Should have DRF-related rules."""
        drf_rules = [r for r in pack.rules if "drf" in r.tags or "viewset" in r.id]
        assert len(drf_rules) > 0


class TestPackComposition:
    """Tests for pack composition."""

    def test_compose_python_and_django(self):
        """Should compose Python and Django packs."""
        packs = get_packs(["python", "django"])

        # Collect all rule IDs
        all_rule_ids = set()
        for pack in packs:
            for rule in pack.rules:
                all_rule_ids.add(rule.id)

        # Should have rules from both packs
        assert any(r.startswith("python/") for r in all_rule_ids)
        assert any(r.startswith("django/") for r in all_rule_ids)

    def test_get_rules_by_tag(self):
        """Should filter rules by tag."""
        pack = get_pack("django")

        security_rules = [r for r in pack.rules if "security" in r.tags]
        performance_rules = [r for r in pack.rules if "performance" in r.tags]

        assert len(security_rules) > 0
        assert len(performance_rules) > 0


class TestRuleTriggers:
    """Tests for rule trigger patterns."""

    @pytest.fixture
    def pack(self):
        """Get Django pack."""
        return get_pack("django")

    def test_n_plus_one_triggers(self, pack):
        """N+1 rule should have file pattern triggers."""
        rule = next(r for r in pack.rules if r.id == "django/n-plus-one")

        assert rule.triggers is not None
        assert len(rule.triggers.file_patterns) > 0

    def test_api_authorization_triggers(self, pack):
        """API authorization rule should have triggers."""
        rule = next(r for r in pack.rules if r.id == "django/api-authorization")

        assert rule.triggers is not None
        assert len(rule.triggers.file_patterns) > 0


class TestCustomRules:
    """Tests for custom YAML rules loading."""

    def test_load_custom_rules_empty_dir(self, tmp_path):
        """Should return empty list for empty directory."""
        rules = load_custom_rules(tmp_path)
        assert rules == []

    def test_load_custom_rules_nonexistent_dir(self, tmp_path):
        """Should return empty list for nonexistent directory."""
        rules = load_custom_rules(tmp_path / "does_not_exist")
        assert rules == []

    def test_load_custom_rules_from_yaml(self, tmp_path):
        """Should load rules from YAML files."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()

        rule_file = rules_dir / "test-rule.yaml"
        rule_file.write_text("""
id: custom/test-rule
name: Test Rule
level: major
category: testing
description: A test rule
checklist:
  - Check this
fix: Fix it like this
tags:
  - test
""")

        rules = load_custom_rules(rules_dir)

        assert len(rules) == 1
        assert rules[0].id == "custom/test-rule"
        assert rules[0].name == "Test Rule"
        assert rules[0].level == IssueLevel.MAJOR
