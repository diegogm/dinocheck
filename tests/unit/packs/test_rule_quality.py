"""Quality gates for every shipped rule.

These tests encode the properties that make a rule useful to the reviewing
agent: parseable, triggerable, self-consistent (its own bad example must
trip its trigger), and complete enough to review against.
"""

import re

import pytest

from dinocheck.packs.loader import get_all_packs

ALL_RULES = [(pack.name, rule) for pack in get_all_packs() for rule in pack.rules]
RULE_IDS = [f"{pack}:{rule.id}" for pack, rule in ALL_RULES]


def test_packs_are_loaded():
    """The built-in packs must load a substantial rule set."""
    assert len(ALL_RULES) >= 100


def test_rule_ids_are_unique():
    ids = [rule.id for _, rule in ALL_RULES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(("pack", "rule"), ALL_RULES, ids=RULE_IDS)
class TestRuleQuality:
    """Per-rule quality invariants."""

    def test_required_fields(self, pack, rule):
        assert rule.name, "rule needs a name"
        assert len(rule.description.strip()) >= 40, "description too short to be useful"
        assert len(rule.checklist) >= 2, "checklist needs at least 2 evaluable items"
        assert len(rule.fix.strip()) >= 20, "fix guidance too short"
        assert rule.tags, "rule needs tags"
        assert rule.category, "rule needs a category"

    def test_has_examples(self, pack, rule):
        assert rule.examples, "rule needs bad/good examples"
        assert rule.examples.get("bad", "").strip(), "missing 'bad' example"
        assert rule.examples.get("good", "").strip(), "missing 'good' example"

    def test_has_triggers(self, pack, rule):
        assert rule.triggers.file_patterns or rule.triggers.code_patterns, (
            "rule without triggers would be briefed for every file"
        )

    def test_code_patterns_compile(self, pack, rule):
        for pattern in rule.triggers.code_patterns:
            re.compile(pattern)

    def test_bad_example_trips_own_trigger(self, pack, rule):
        """A rule whose own bad example doesn't match its code patterns
        would never be briefed for the very code it warns about."""
        patterns = rule.triggers.code_patterns
        if not patterns:
            pytest.skip("rule triggers on file patterns only")
        bad = rule.examples["bad"]
        assert any(re.search(p, bad) for p in patterns), (
            f"no code_pattern matches the rule's own bad example: {patterns}"
        )

    def test_checklist_items_are_strings(self, pack, rule):
        """Unquoted 'key: value' text in YAML silently parses as a dict."""
        for item in rule.checklist:
            assert isinstance(item, str), f"checklist item parsed as {type(item).__name__}"
