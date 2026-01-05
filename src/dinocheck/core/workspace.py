"""Workspace scanning and git diff integration."""

import re
from collections.abc import Iterator
from pathlib import Path

import git

from dinocheck.core.interfaces import WorkspaceScanner as IWorkspaceScanner
from dinocheck.core.types import DiffHunk, FileContext


class GitWorkspaceScanner(IWorkspaceScanner):
    """Scans workspace for files using git for diff detection."""

    def __init__(self, repo_path: Path | None = None):
        self.repo_path = repo_path or Path.cwd()
        self._repo: git.Repo | None = None

    @property
    def repo(self) -> git.Repo | None:
        """Get git repo, caching the result."""
        if self._repo is None:
            try:
                self._repo = git.Repo(self.repo_path, search_parent_directories=True)
            except git.InvalidGitRepositoryError:
                self._repo = None
        return self._repo

    def discover(
        self,
        paths: list[Path],
        diff_only: bool = True,
    ) -> Iterator[FileContext]:
        """
        Discover files to analyze.

        If paths is empty and diff_only is True, discovers changed files.
        Otherwise, discovers files from provided paths.
        """
        if not paths and diff_only:
            # Get changed files from git
            yield from self._discover_changed_files()
        elif paths:
            # Use provided paths
            for path in paths:
                if path.is_file():
                    yield from self._file_to_context(path, diff_only)
                elif path.is_dir():
                    yield from self._discover_directory(path, diff_only)
        else:
            # Discover all Python files in current directory
            yield from self._discover_directory(Path.cwd(), diff_only)

    def _discover_changed_files(self) -> Iterator[FileContext]:
        """Discover files changed in git."""
        if not self.repo:
            return

        # Get staged and unstaged changes
        try:
            # Changed files (staged and unstaged)
            changed: set[Path] = set()

            # Unstaged changes
            for item in self.repo.index.diff(None):
                if item.a_path and item.a_path.endswith(".py"):
                    changed.add(Path(item.a_path))

            # Staged changes (only if there are commits)
            try:
                _ = self.repo.head.commit  # Check if HEAD exists
                for item in self.repo.index.diff("HEAD"):
                    if item.a_path and item.a_path.endswith(".py"):
                        changed.add(Path(item.a_path))
                    if item.b_path and item.b_path.endswith(".py"):
                        changed.add(Path(item.b_path))
            except ValueError:
                # No commits yet, skip staged diff against HEAD
                pass

            # Untracked files
            for untracked in self.repo.untracked_files:
                if untracked.endswith(".py"):
                    changed.add(Path(untracked))

            for file_path in changed:
                # Git paths are relative to repo root, not self.repo_path
                repo_root = Path(str(self.repo.working_dir))
                full_path = repo_root / file_path
                if full_path.exists():
                    yield from self._file_to_context(full_path, diff_only=True)

        except git.GitCommandError:
            # If git fails, fall back to no files
            pass

    def _discover_directory(self, directory: Path, diff_only: bool) -> Iterator[FileContext]:
        """Discover Python files in a directory."""
        for path in directory.rglob("*.py"):
            # Skip hidden directories and common excludes
            # Note: exclude ".." and "." from the check (they're navigation, not hidden)
            if any(part.startswith(".") and part not in (".", "..") for part in path.parts):
                continue
            if any(part in ("__pycache__", "node_modules", ".venv", "venv") for part in path.parts):
                continue

            yield from self._file_to_context(path, diff_only)

    def _file_to_context(self, path: Path, diff_only: bool) -> Iterator[FileContext]:
        """Convert a file path to FileContext."""
        try:
            content = path.read_text()
        except (OSError, UnicodeDecodeError):
            return

        diff_hunks = []
        is_new = False

        if diff_only and self.repo:
            diff_hunks = self.get_diff_hunks(path)
            is_new = self._is_new_file(path)

        yield FileContext(
            path=path,
            content=content,
            diff_hunks=diff_hunks,
            is_new=is_new,
        )

    def get_diff_hunks(self, path: Path) -> list[DiffHunk]:
        """Get diff hunks for a file."""
        if not self.repo:
            return []

        try:
            # Get diff against HEAD
            working_dir = self.repo.working_dir
            relative_path = path.relative_to(Path(str(working_dir)))
            diff = self.repo.git.diff("HEAD", "--", str(relative_path), unified=3)

            if not diff:
                # Check if file is untracked/new
                diff = self.repo.git.diff("--no-index", "/dev/null", str(path), unified=3)
                if not diff:
                    return []

            return self._parse_diff(diff)

        except (git.GitCommandError, ValueError):
            return []

    def _parse_diff(self, diff_text: str) -> list[DiffHunk]:
        """Parse unified diff into hunks."""
        hunks: list[DiffHunk] = []
        current_start: int = 0
        current_end: int = 0
        current_header: str = ""
        current_lines: list[str] = []
        in_hunk = False

        for line in diff_text.split("\n"):
            # Hunk header: @@ -start,count +start,count @@
            hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@(.*)$", line)
            if hunk_match:
                if in_hunk:
                    hunks.append(
                        DiffHunk(
                            start_line=current_start,
                            end_line=current_end,
                            content="\n".join(current_lines),
                            header=current_header,
                        )
                    )

                current_start = int(hunk_match.group(1))
                count = int(hunk_match.group(2) or 1)
                current_end = current_start + count - 1
                current_header = hunk_match.group(3).strip()
                current_lines = []
                in_hunk = True

            elif in_hunk:
                if line.startswith("+") and not line.startswith("+++"):
                    current_lines.append(line[1:])
                elif line.startswith("-") and not line.startswith("---"):
                    pass  # Removed line
                elif line.startswith(" "):
                    current_lines.append(line[1:])

        if in_hunk:
            hunks.append(
                DiffHunk(
                    start_line=current_start,
                    end_line=current_end,
                    content="\n".join(current_lines),
                    header=current_header,
                )
            )

        return hunks

    def _is_new_file(self, path: Path) -> bool:
        """Check if a file is new (untracked or staged but not yet committed)."""
        if not self.repo:
            # Without git context, we can't determine if file is new
            return False

        try:
            relative_path = str(path.relative_to(self.repo.working_dir))

            # Check if untracked
            if relative_path in self.repo.untracked_files:
                return True

            # Check if staged but new (exists in index but not in HEAD)
            try:
                # Get staged changes against HEAD
                for diff in self.repo.index.diff("HEAD"):
                    # new_file means it exists in index but not in HEAD
                    if diff.new_file and diff.b_path == relative_path:
                        return True
            except ValueError:
                # No HEAD yet (empty repo), all staged files are new
                if relative_path in [e.path for e in self.repo.index.entries.values()]:
                    return True

            return False
        except (ValueError, git.GitCommandError):
            return False
