"""Source file discovery and AST-based analysis for test coverage gaps.

Finds service/repository files in configured source directories and
provides AST-based counting of public methods and test functions.

See: docs/_shared/CONSTRAINTS.md (RULE-10)
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Three parents up: test_coverage_gaps/discovery.py -> test_coverage_gaps/ -> scripts/ -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Source directories to scan for service/repository files.
SOURCE_SCAN_DIRS: list[tuple[Path, str]] = [
    (REPO_ROOT / "apps" / "api" / "narrare", "api"),
    (REPO_ROOT / "packages" / "core" / "narrare_core", "core"),
]

# Glob patterns for source files.
SOURCE_PATTERNS: list[str] = ["service*.py", "repository*.py"]

# Files to skip.
SKIP_NAMES: frozenset[str] = frozenset({"__init__.py", "conftest.py"})

# Default test directory root.
DEFAULT_TEST_ROOT = REPO_ROOT / "tests" / "unit"

# Default low-coverage threshold (ratio of test functions to public methods).
DEFAULT_THRESHOLD: float = 0.5


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class AnalysisConfig:
    """Runtime configuration passed through the analysis pipeline."""

    test_root: Path = DEFAULT_TEST_ROOT
    threshold: float = DEFAULT_THRESHOLD


@dataclass
class SourceFile:
    """A source file (service/repository) with analysis results."""

    path: Path
    domain: str  # e.g. "kb", "writing", "token_limits"
    layer: str  # "api" or "core"
    parent_domain: str = ""  # e.g. "settings" for nested modules
    config: AnalysisConfig = field(default_factory=AnalysisConfig)
    public_methods: int = 0
    test_files: list[Path] = field(default_factory=list[Path])
    test_functions: int = 0

    @property
    def has_tests(self) -> bool:
        return len(self.test_files) > 0

    @property
    def coverage_ratio(self) -> float:
        if self.public_methods == 0:
            return 1.0
        return self.test_functions / self.public_methods

    @property
    def status(self) -> str:
        if not self.has_tests:
            return "missing"
        if self.coverage_ratio < self.config.threshold and self.public_methods > 0:
            return "low"
        return "ok"

    @property
    def display_path(self) -> str:
        try:
            return self.path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return self.path.as_posix()

    @property
    def test_display_paths(self) -> str:
        if not self.test_files:
            return "NO TEST FILE FOUND"
        return ", ".join(t.relative_to(REPO_ROOT).as_posix() for t in self.test_files)


# ---------------------------------------------------------------------------
# Source file discovery
# ---------------------------------------------------------------------------


def _should_skip(path: Path) -> bool:
    """Return True if the file should be skipped."""
    return path.name in SKIP_NAMES or path.name.endswith(("_schemas.py", "_types.py"))


def discover_source_files(
    source_dirs: list[tuple[Path, str]] | None = None,
    config: AnalysisConfig | None = None,
) -> list[SourceFile]:
    """Find all service and repository files in the configured directories."""
    if source_dirs is None:
        source_dirs = SOURCE_SCAN_DIRS
    if config is None:
        config = AnalysisConfig()

    files: list[SourceFile] = []
    seen: set[Path] = set()

    for base_dir, layer in source_dirs:
        if not base_dir.exists():
            continue

        for pattern in SOURCE_PATTERNS:
            for match in base_dir.rglob(pattern):
                if _should_skip(match) or match in seen:
                    continue

                # Derive domain from parent directory name.
                try:
                    relative = match.relative_to(base_dir)
                    # Use immediate parent directory as domain.
                    domain = match.parent.name
                    # Check for nested modules (e.g. settings/token_limits).
                    parent_parts = relative.parent.parts
                    parent_domain = parent_parts[0] if len(parent_parts) > 1 else ""
                except ValueError:
                    domain = "unknown"
                    parent_domain = ""

                files.append(
                    SourceFile(
                        path=match,
                        domain=domain,
                        layer=layer,
                        parent_domain=parent_domain,
                        config=config,
                    )
                )
                seen.add(match)

    return sorted(files, key=lambda f: f.display_path)


# ---------------------------------------------------------------------------
# AST-based analysis
# ---------------------------------------------------------------------------


def _parse_file(path: Path) -> ast.Module | None:
    """Parse a Python file safely, returning None on syntax errors."""
    try:
        source = path.read_text(encoding="utf-8")
        if not source.strip():
            return None
        return ast.parse(source, filename=str(path))
    except SyntaxError, UnicodeDecodeError:
        return None


def count_public_methods(path: Path) -> int:
    """Count public methods and top-level async functions in a source file.

    Counts:
    - Top-level ``async def`` functions (public, not starting with ``_``)
    - Class methods (public, not starting with ``_``) in service/repository
      classes

    Uses ``tree.body`` iteration instead of ``ast.walk`` to avoid
    double-counting class methods.
    """
    tree = _parse_file(path)
    if tree is None:
        return 0

    count = 0

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                count += 1
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for item in node.body:
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and not item.name.startswith("_"):
                    count += 1

    return count


def count_test_functions(path: Path) -> int:
    """Count test functions (``test_*``) in a test file."""
    tree = _parse_file(path)
    if tree is None:
        return 0

    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            count += 1
    return count
