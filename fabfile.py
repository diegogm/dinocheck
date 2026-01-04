"""Development tasks for Dinocheck.

Usage:
    fab test          # Run all tests
    fab lint          # Run linters (ruff + mypy)
    fab format        # Format code with ruff
    fab check         # Run all checks (lint + test)
    fab build         # Build package
    fab clean         # Clean build artifacts
    fab predeploy     # Run pre-deploy checks (ruff strict + tests)
    fab publish       # Publish to PyPI (runs predeploy first)
    fab dino          # Run dino CLI (e.g., fab dino -- check src/)
"""

import os

from fabric import task
from rich.console import Console

# Rich console for colored output
console = Console()

# Constants
PYTHON_VERSION = "3.12"
SOURCE_DIRS = "src/ tests/"
PACKAGE_DIR = "src/dinocheck/"
TESTS_DIR = "tests/"
BUILD_ARTIFACTS = "dist/ build/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/"
COVERAGE_SOURCE = "src/dinocheck"

# Ensure ~/.local/bin is in PATH for uv
UV_PATH = os.path.expanduser("~/.local/bin")
ENV_PATH = {"PATH": f"{UV_PATH}:{os.environ.get('PATH', '')}"}


def _run(c, cmd: str, **kwargs):
    """Run command with proper environment."""
    return c.run(cmd, env=ENV_PATH, **kwargs)


def _uv_run(cmd: str) -> str:
    """Build uv run command with Python version."""
    return f"uv run --python {PYTHON_VERSION} {cmd}"


def _banner(title: str) -> None:
    """Print a banner with separators."""
    console.print()
    console.rule(title, style="cyan")


def _step(message: str) -> None:
    """Print a step message."""
    console.print(f"[bold blue]>>>[/bold blue] {message}")


def _success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def _error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]✗[/bold red] {message}")


@task
def test(c, cov=False, verbose=False, markers=None):
    """Run tests with pytest.

    Args:
        cov: Enable coverage reporting
        verbose: Show verbose output
        markers: Run only tests with given markers (e.g., 'not slow')
    """
    cmd = f"pytest {TESTS_DIR}"
    if cov:
        cmd += f" --cov={COVERAGE_SOURCE} --cov-report=term-missing --cov-report=xml"
    if verbose:
        cmd += " -v"
    if markers:
        cmd += f" -m '{markers}'"
    _run(c, _uv_run(cmd))


@task
def lint(c, fix=False):
    """Run linters (ruff + mypy).

    Args:
        fix: Auto-fix issues where possible
    """
    ruff_cmd = f"ruff check {SOURCE_DIRS}"
    if fix:
        ruff_cmd += " --fix"
    result = _run(c, _uv_run(ruff_cmd), warn=True)
    mypy_result = _run(c, _uv_run(f"mypy {PACKAGE_DIR}"), warn=True)

    if result.ok and mypy_result.ok:
        _success("All checks passed!")


@task
def format(c):
    """Format code with ruff."""
    _run(c, _uv_run(f"ruff format {SOURCE_DIRS}"))
    _run(c, _uv_run(f"ruff check {SOURCE_DIRS} --fix"))
    _success("Code formatted!")


@task
def check(c):
    """Run all checks (lint + test)."""
    lint(c)
    test(c)


@task
def build(c):
    """Build package for distribution."""
    clean(c)
    _run(c, "uv build")
    _success("Package built!")


@task
def clean(c):
    """Clean build artifacts."""
    _run(c, f"rm -rf {BUILD_ARTIFACTS}")
    _run(c, "find . -type d -name __pycache__ -exec rm -rf {} +", warn=True)
    _run(c, "find . -type f -name '*.pyc' -delete", warn=True)
    _success("Cleaned build artifacts!")


@task
def install(c):
    """Install package in development mode."""
    _run(c, "uv sync --dev")
    _success("Dependencies installed!")


@task
def typecheck(c):
    """Run mypy type checking."""
    _run(c, _uv_run(f"mypy {PACKAGE_DIR}"))


@task
def predeploy(c):
    """Run pre-deployment checks (strict ruff + tests).

    This task ensures code quality before publishing:
    - Ruff linting with no warnings allowed
    - All tests must pass
    """
    _banner("Pre-deploy Checks")

    _step("Checking code with ruff (strict mode)")
    result = _run(c, _uv_run(f"ruff check {SOURCE_DIRS}"), warn=True)
    if result.failed:
        _error("Ruff found issues. Fix them before deploying.")
        raise SystemExit(1)

    _step("Checking code format with ruff")
    result = _run(c, _uv_run(f"ruff format {SOURCE_DIRS} --check"), warn=True)
    if result.failed:
        _error("Code is not formatted. Run 'fab format' first.")
        raise SystemExit(1)

    _step("Running all tests")
    test(c)

    console.print()
    _banner("Pre-deploy Passed")
    _success("Ready to publish!")


@task
def publish(c, test_pypi=False, skip_checks=False):
    """Publish package to PyPI.

    Args:
        test_pypi: Publish to TestPyPI instead of PyPI
        skip_checks: Skip pre-deploy checks (not recommended)
    """
    if not skip_checks:
        predeploy(c)

    build(c)
    if test_pypi:
        _run(c, "uv publish --publish-url https://test.pypi.org/legacy/")
    else:
        _run(c, "uv publish")
    _success("Published to PyPI!")


@task
def dino(c, args=""):
    """Run dino CLI with arguments.

    Examples:
        fab dino -a version         # Show version
        fab dino -a "check src/"    # Run check on src/
        fab dino -a "packs list"    # List packs
    """
    _run(c, _uv_run(f"dino {args}"))


@task
def ci(c):
    """Run CI pipeline locally."""
    _banner("CI Pipeline")

    _step("Installing dependencies")
    install(c)

    _step("Running linters")
    lint(c)

    _step("Running tests with coverage")
    test(c, cov=True)

    _step("Building package")
    build(c)

    console.print()
    _banner("CI Passed")
    _success("All checks passed!")
