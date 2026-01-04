"""Tests for workspace scanner."""


import pytest

from dinocrit.core.workspace import GitWorkspaceScanner


class TestWorkspaceScanner:
    """Tests for GitWorkspaceScanner class."""

    @pytest.fixture
    def scanner(self):
        """Create a workspace scanner."""
        return GitWorkspaceScanner()

    def test_discover_single_file(self, scanner, tmp_path):
        """Should discover a single Python file."""
        file_path = tmp_path / "test.py"
        file_path.write_text("x = 1")

        files = list(scanner.discover([file_path], diff_only=False))

        assert len(files) == 1
        assert files[0].path == file_path

    def test_discover_directory(self, scanner, tmp_path):
        """Should discover Python files in directory."""
        (tmp_path / "file1.py").write_text("x = 1")
        (tmp_path / "file2.py").write_text("y = 2")
        (tmp_path / "readme.md").write_text("# Readme")

        files = list(scanner.discover([tmp_path], diff_only=False))

        # Should find Python files, not markdown
        py_files = [f for f in files if f.path.suffix == ".py"]
        assert len(py_files) >= 2

    def test_discover_excludes_non_python(self, scanner, tmp_path):
        """Should exclude non-Python files by default."""
        (tmp_path / "script.py").write_text("x = 1")
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "style.css").write_text("body {}")

        files = list(scanner.discover([tmp_path], diff_only=False))

        # All discovered files should be Python
        for f in files:
            assert f.path.suffix == ".py"

    def test_discover_nested_directories(self, scanner, tmp_path):
        """Should discover files in nested directories."""
        nested = tmp_path / "src" / "app"
        nested.mkdir(parents=True)
        (nested / "views.py").write_text("def view(): pass")

        files = list(scanner.discover([tmp_path], diff_only=False))

        assert any(f.path.name == "views.py" for f in files)

    def test_discover_excludes_pycache(self, scanner, tmp_path):
        """Should exclude __pycache__ directories."""
        (tmp_path / "good.py").write_text("x = 1")

        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.cpython-311.pyc").write_text("")

        files = list(scanner.discover([tmp_path], diff_only=False))

        # Should not include __pycache__ files
        for f in files:
            assert "__pycache__" not in str(f.path)

    def test_file_context_content(self, scanner, tmp_path):
        """FileContext should include file content."""
        file_path = tmp_path / "test.py"
        content = "def hello():\n    return 'world'"
        file_path.write_text(content)

        files = list(scanner.discover([file_path], diff_only=False))

        assert len(files) == 1
        assert files[0].content == content

    def test_discover_empty_directory(self, scanner, tmp_path):
        """Should handle empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        files = list(scanner.discover([empty_dir], diff_only=False))

        assert files == []

    def test_discover_nonexistent_path(self, scanner, tmp_path):
        """Should handle nonexistent path gracefully."""
        nonexistent = tmp_path / "does_not_exist.py"

        files = list(scanner.discover([nonexistent], diff_only=False))

        assert files == []


class TestGitDiffIntegration:
    """Tests for git diff integration."""

    @pytest.fixture
    def git_repo(self, empty_git_repo):
        """Use the empty git repo fixture."""
        return empty_git_repo

    def test_discover_changed_files(self, git_repo):
        """Should discover changed files in git repo."""
        import subprocess

        # Create and commit a file
        file_path = git_repo / "initial.py"
        file_path.write_text("x = 1")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=git_repo,
            capture_output=True,
        )

        # Modify the file
        file_path.write_text("x = 2")

        scanner = GitWorkspaceScanner(repo_path=git_repo)
        files = list(scanner.discover([], diff_only=True))

        assert any(f.path.name == "initial.py" for f in files)

    def test_discover_new_files(self, git_repo):
        """Should discover new untracked files."""
        # Create a new untracked file
        new_file = git_repo / "new_file.py"
        new_file.write_text("y = 1")

        scanner = GitWorkspaceScanner(repo_path=git_repo)
        files = list(scanner.discover([], diff_only=True))

        assert any(f.path.name == "new_file.py" for f in files)

    def test_discover_no_changes(self, git_repo):
        """Should return empty list when no changes."""
        import subprocess

        # Create and commit a file
        file_path = git_repo / "committed.py"
        file_path.write_text("x = 1")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "commit"],
            cwd=git_repo,
            capture_output=True,
        )

        scanner = GitWorkspaceScanner(repo_path=git_repo)
        files = list(scanner.discover([], diff_only=True))

        # Should be empty since all files are committed
        assert not any(f.path.name == "committed.py" for f in files)
