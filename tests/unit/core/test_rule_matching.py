"""Tests for rule-to-file matching semantics."""

from pathlib import Path

from dinocheck.core.types import IssueLevel, Rule, RuleTrigger
from dinocheck.packs.loader import ComposedPack


def _rule(rule_id="t/rule", file_patterns=None, code_patterns=None):
    return Rule(
        id=rule_id,
        name="Test rule",
        level=IssueLevel.MAJOR,
        category="test",
        description="desc",
        checklist=["check"],
        fix="fix",
        triggers=RuleTrigger(
            file_patterns=file_patterns or [],
            code_patterns=code_patterns or [],
        ),
    )


def _pack(*rules):
    return ComposedPack(name="test", version="t", rules_dict={r.id: r for r in rules})


class TestFilePatternMatching:
    """Tests for the '**/x matches root-level x' semantics."""

    def test_double_star_matches_nested(self):
        pack = _pack(_rule(file_patterns=["**/views.py"]))
        assert pack.get_rules_for_file(Path("app/views.py"), "") != []

    def test_double_star_matches_root_level(self):
        """**/Dockerfile must match a repo-root Dockerfile (the common case)."""
        pack = _pack(_rule(file_patterns=["**/Dockerfile"]))
        assert pack.get_rules_for_file(Path("Dockerfile"), "") != []

    def test_double_star_root_level_views(self):
        pack = _pack(_rule(file_patterns=["**/views.py"]))
        assert pack.get_rules_for_file(Path("views.py"), "") != []

    def test_non_matching_file(self):
        pack = _pack(_rule(file_patterns=["**/*.py"]))
        assert pack.get_rules_for_file(Path("style.css"), "") == []

    def test_code_pattern_still_required(self):
        pack = _pack(_rule(file_patterns=["**/*.py"], code_patterns=[r"objects\."]))
        assert pack.get_rules_for_file(Path("a.py"), "x = 1") == []
        assert pack.get_rules_for_file(Path("a.py"), "Book.objects.all()") != []


class TestCandidateFiles:
    """Tests for discovery pre-filtering by pack patterns."""

    def test_candidate_by_suffix(self):
        pack = _pack(_rule(file_patterns=["**/*.tsx"]))
        assert pack.is_candidate_file(Path("src/App.tsx"))
        assert not pack.is_candidate_file(Path("src/app.py"))

    def test_candidate_root_level(self):
        pack = _pack(_rule(file_patterns=["**/docker-compose*.yml"]))
        assert pack.is_candidate_file(Path("docker-compose.yml"))

    def test_rule_without_file_patterns_matches_everything(self):
        pack = _pack(_rule(code_patterns=["TODO"]))
        assert pack.is_candidate_file(Path("anything.xyz"))


class TestRuleFingerprint:
    """Tests for content-addressed rule identity."""

    def test_same_content_same_fingerprint(self):
        assert _rule().fingerprint == _rule().fingerprint

    def test_editing_text_changes_fingerprint(self):
        a = _rule()
        b = _rule()
        b.checklist = ["check", "another check"]
        assert a.fingerprint != b.fingerprint

    def test_changing_level_changes_fingerprint(self):
        a = _rule()
        b = _rule()
        b.level = IssueLevel.BLOCKER
        assert a.fingerprint != b.fingerprint

    def test_fingerprint_is_prefixed_by_id(self):
        assert _rule(rule_id="pack/x").fingerprint.startswith("pack/x:")
