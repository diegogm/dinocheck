"""Tests for workspace scanner."""

import pytest

from dinocheck.core.workspace import GitWorkspaceScanner


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


class TestExcludePatterns:
    """Tests for exclude_patterns filtering."""

    def test_exclude_directory_by_name(self, tmp_path):
        """Should exclude directories matching pattern."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1")
        (tmp_path / "migrations").mkdir()
        (tmp_path / "migrations" / "0001_initial.py").write_text("y = 2")

        scanner = GitWorkspaceScanner(exclude_patterns=["migrations"])
        files = list(scanner.discover([tmp_path], diff_only=False))

        paths = [f.path.name for f in files]
        assert "app.py" in paths
        assert "0001_initial.py" not in paths

    def test_exclude_nested_directory(self, tmp_path):
        """Should exclude nested directories matching pattern."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "views.py").write_text("x = 1")
        nested = tmp_path / "src" / "app" / "migrations"
        nested.mkdir(parents=True)
        (nested / "0001.py").write_text("y = 2")

        scanner = GitWorkspaceScanner(exclude_patterns=["migrations"])
        files = list(scanner.discover([tmp_path], diff_only=False))

        paths = [f.path.name for f in files]
        assert "views.py" in paths
        assert "0001.py" not in paths

    def test_exclude_file_pattern(self, tmp_path):
        """Should exclude files matching glob pattern."""
        (tmp_path / "views.py").write_text("x = 1")
        (tmp_path / "views_test.py").write_text("y = 2")

        scanner = GitWorkspaceScanner(exclude_patterns=["*_test.py"])
        files = list(scanner.discover([tmp_path], diff_only=False))

        paths = [f.path.name for f in files]
        assert "views.py" in paths
        assert "views_test.py" not in paths

    def test_exclude_multiple_patterns(self, tmp_path):
        """Should support multiple exclude patterns."""
        (tmp_path / "app.py").write_text("x = 1")
        (tmp_path / "migrations").mkdir()
        (tmp_path / "migrations" / "0001.py").write_text("y = 2")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_app.py").write_text("z = 3")

        scanner = GitWorkspaceScanner(exclude_patterns=["migrations", "tests"])
        files = list(scanner.discover([tmp_path], diff_only=False))

        paths = [f.path.name for f in files]
        assert "app.py" in paths
        assert "0001.py" not in paths
        assert "test_app.py" not in paths

    def test_exclude_relative_path_pattern(self, tmp_path):
        """Should exclude files matching a path-style pattern like tests/fixtures."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1")
        fixtures = tmp_path / "tests" / "fixtures"
        fixtures.mkdir(parents=True)
        (fixtures / "data.py").write_text("y = 2")
        (tmp_path / "tests" / "test_app.py").write_text("z = 3")

        scanner = GitWorkspaceScanner(repo_path=tmp_path, exclude_patterns=["tests/fixtures"])
        files = list(scanner.discover([tmp_path], diff_only=False))

        paths = [f.path.name for f in files]
        assert "app.py" in paths
        assert "test_app.py" in paths
        assert "data.py" not in paths

    def test_exclude_path_pattern_when_scanning_subdirectory(self, tmp_path):
        """Should exclude using repo-relative paths even when scanning a subdirectory."""
        # Create: project/tests/fixtures/data.py and project/tests/test_app.py
        fixtures = tmp_path / "tests" / "fixtures"
        fixtures.mkdir(parents=True)
        (fixtures / "data.py").write_text("y = 2")
        (tmp_path / "tests" / "test_app.py").write_text("z = 3")

        # Scan the "tests/" subdirectory with a path-style pattern
        scanner = GitWorkspaceScanner(
            repo_path=tmp_path,
            exclude_patterns=["tests/fixtures"],
        )
        files = list(scanner.discover([tmp_path / "tests"], diff_only=False))

        paths = [f.path.name for f in files]
        assert "test_app.py" in paths
        assert "data.py" not in paths

    def test_no_exclude_patterns(self, tmp_path):
        """Should discover all files when no exclude patterns."""
        (tmp_path / "app.py").write_text("x = 1")
        (tmp_path / "migrations").mkdir()
        (tmp_path / "migrations" / "0001.py").write_text("y = 2")

        scanner = GitWorkspaceScanner()
        files = list(scanner.discover([tmp_path], diff_only=False))

        paths = [f.path.name for f in files]
        assert "app.py" in paths
        assert "0001.py" in paths

    def test_exclude_with_diff_mode(self, empty_git_repo):
        """Should apply exclude patterns in diff mode too."""
        import subprocess

        repo = empty_git_repo

        # Create and commit initial files
        (repo / "app.py").write_text("x = 1")
        (repo / "migrations").mkdir()
        (repo / "migrations" / "0001.py").write_text("y = 1")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo,
            capture_output=True,
        )

        # Modify both files
        (repo / "app.py").write_text("x = 2")
        (repo / "migrations" / "0001.py").write_text("y = 2")

        scanner = GitWorkspaceScanner(repo_path=repo, exclude_patterns=["migrations"])
        files = list(scanner.discover([], diff_only=True))

        paths = [f.path.name for f in files]
        assert "app.py" in paths
        assert "0001.py" not in paths


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
        assert len(files) == 0, f"Expected no files, got: {[f.path.name for f in files]}"
