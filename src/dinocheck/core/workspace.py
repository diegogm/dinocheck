"""Workspace scanning and git diff integration."""

import contextlib
import logging
import re
from collections.abc import Callable, Iterator
from fnmatch import fnmatch
from pathlib import Path

import git

from dinocheck.core.interfaces import WorkspaceScanner as IWorkspaceScanner
from dinocheck.core.types import DiffHunk, FileContext

logger = logging.getLogger("dinocheck")

# Files larger than this are never analyzed (generated bundles, data dumps)
MAX_FILE_SIZE_BYTES = 1_000_000


class GitWorkspaceScanner(IWorkspaceScanner):
    """Scans workspace for files using git for diff detection."""

    def __init__(
        self,
        repo_path: Path | None = None,
        exclude_patterns: list[str] | None = None,
    ):
        self.repo_path = repo_path or Path.cwd()
        self.exclude_patterns = exclude_patterns or []
        self._repo: git.Repo | None = None
        self._index_paths: set[str] | None = None

    @property
    def repo(self) -> git.Repo | None:
        """Get git repo, caching the result."""
        if self._repo is None:
            try:
                self._repo = git.Repo(self.repo_path, search_parent_directories=True)
            except git.InvalidGitRepositoryError:
                self._repo = None
        return self._repo

    @property
    def _exclude_base(self) -> Path:
        """Base directory for exclude pattern matching (repo root or cwd)."""
        if self.repo:
            return Path(str(self.repo.working_dir))
        return self.repo_path

    @property
    def index_paths(self) -> set[str]:
        """Get set of paths in git index, caching the result."""
        if self._index_paths is None:
            if self.repo:
                self._index_paths = {str(e.path) for e in self.repo.index.entries.values()}
            else:
                self._index_paths = set()
        return self._index_paths

    def discover(
        self,
        paths: list[Path],
        diff_only: bool = True,
        is_candidate: Callable[[Path], bool] | None = None,
    ) -> Iterator[FileContext]:
        """
        Discover files to analyze.

        If paths is empty and diff_only is True, discovers changed files.
        Otherwise, discovers files from provided paths. is_candidate filters
        walked and changed files by path; explicit file paths bypass it.
        """
        if not paths and diff_only:
            # Get changed files from git
            yield from self._discover_changed_files(is_candidate)
        elif paths:
            # Use provided paths
            for path in paths:
                if path.is_file():
                    # Explicitly requested - never filtered out
                    yield from self._file_to_context(path, diff_only)
                elif path.is_dir():
                    yield from self._discover_directory(path, diff_only, is_candidate)
        else:
            # Discover files in current directory
            yield from self._discover_directory(Path.cwd(), diff_only, is_candidate)

    def _discover_changed_files(
        self, is_candidate: Callable[[Path], bool] | None
    ) -> Iterator[FileContext]:
        """Discover files changed in git (staged, unstaged, and untracked)."""
        if not self.repo:
            return

        try:
            # Changed files (staged and unstaged)
            changed: set[Path] = set()

            # Unstaged changes (include b_path for renames)
            for item in self.repo.index.diff(None):
                if item.a_path:
                    changed.add(Path(item.a_path))
                if item.b_path:
                    changed.add(Path(item.b_path))

            # Staged changes - check if HEAD exists
            has_head = False
            with contextlib.suppress(ValueError):
                # ValueError raised for empty repo with no HEAD reference
                has_head = self.repo.head.is_valid()

            if has_head:
                # Has commits - diff against HEAD
                for item in self.repo.index.diff("HEAD"):
                    if item.a_path:
                        changed.add(Path(item.a_path))
                    if item.b_path:
                        changed.add(Path(item.b_path))
            else:
                # No commits yet - all staged files are new
                for entry in self.repo.index.entries.values():
                    changed.add(Path(str(entry.path)))

            # Untracked files
            for untracked in self.repo.untracked_files:
                changed.add(Path(untracked))

            repo_root = Path(str(self.repo.working_dir))
            for file_path in changed:
                if is_candidate and not is_candidate(file_path):
                    continue
                # Git paths are relative to repo root, not self.repo_path
                full_path = repo_root / file_path
                if (
                    full_path.exists()
                    and not self._should_exclude(full_path)
                    and not self._too_large(full_path)
                ):
                    # Prefer cwd-relative paths: cleaner briefs, and the agent
                    # reports the same path back to `dino report`
                    try:
                        context_path = full_path.relative_to(Path.cwd())
                    except ValueError:
                        context_path = full_path
                    yield from self._file_to_context(context_path, diff_only=True)

        except git.GitCommandError as e:
            logger.warning("Git diff failed, no changed files discovered: %s", e)

    @staticmethod
    def _too_large(path: Path) -> bool:
        """Check whether a file exceeds the analysis size limit."""
        try:
            if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                logger.warning("Skipping %s: larger than %d bytes", path, MAX_FILE_SIZE_BYTES)
                return True
        except OSError:
            return True
        return False

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded based on exclude_patterns.

        Patterns are matched against paths relative to the repo/project root,
        ensuring consistent behavior regardless of which subdirectory is scanned.

        Matching modes:
        - Individual directory/file name components (e.g., "migrations" matches any dir named migrations)
        - The full relative path and all parent paths via fnmatch
          (e.g., "tests/fixtures" matches tests/fixtures/data.py)
        """
        if not self.exclude_patterns:
            return False

        try:
            relative = path.resolve().relative_to(self._exclude_base.resolve())
        except ValueError:
            relative = path

        for pattern in self.exclude_patterns:
            # Match against any path component (directory or filename)
            if any(fnmatch(part, pattern) for part in relative.parts):
                return True
            # Match against the full relative path and all parent paths
            current = relative
            while True:
                if fnmatch(str(current), pattern):
                    return True
                parent = current.parent
                if parent == current:
                    break
                current = parent

        return False

    def _discover_directory(
        self,
        directory: Path,
        diff_only: bool,
        is_candidate: Callable[[Path], bool] | None,
    ) -> Iterator[FileContext]:
        """Discover analyzable files in a directory.

        Walks every file and lets is_candidate (rule pack file patterns)
        decide what is relevant - dinocheck is not Python-only.
        """
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            # Skip hidden directories and common excludes
            # Note: exclude ".." and "." from the check (they're navigation, not hidden)
            if any(part.startswith(".") and part not in (".", "..") for part in path.parts):
                continue
            if any(part in ("__pycache__", "node_modules", ".venv", "venv") for part in path.parts):
                continue
            if self._should_exclude(path):
                continue
            if is_candidate and not is_candidate(path):
                continue
            if self._too_large(path):
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
            working_dir = Path(str(self.repo.working_dir))
            # Resolve to absolute path to handle relative paths
            abs_path = path.resolve() if not path.is_absolute() else path
            relative_path = abs_path.relative_to(working_dir)

            # Check if HEAD exists (repo has at least one commit)
            has_head = self.repo.head.is_valid()
            if has_head:
                # unified=0: hunk ranges cover exactly the changed lines
                diff = self.repo.git.diff("HEAD", "--", str(relative_path), unified=0)
            else:
                # Empty repo without HEAD - treat file as new
                diff = None

            if not diff:
                # Check if file is untracked/new
                with contextlib.suppress(git.GitCommandError):
                    # --no-index exits with 1 when there are differences, but still outputs diff
                    diff = self.repo.git.diff("--no-index", "/dev/null", str(path), unified=0)
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

                current_start = max(1, int(hunk_match.group(1)))
                count = int(hunk_match.group(2) or 1)
                # A pure deletion has count 0: mark the line where it happened
                current_end = max(current_start, current_start + count - 1)
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
            # Resolve to absolute path to handle relative paths
            abs_path = path.resolve() if not path.is_absolute() else path
            # Use as_posix() for cross-platform compatibility (git always uses forward slashes)
            relative_path = abs_path.relative_to(self.repo.working_dir).as_posix()

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
                if relative_path in self.index_paths:
                    return True

            return False
        except (ValueError, git.GitCommandError):
            return False
