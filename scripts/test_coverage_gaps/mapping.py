"""Test file mapping for source files.

Maps source files (services/repositories) to their corresponding test files
using multiple naming convention patterns and directory scanning.

See: docs/_shared/CONSTRAINTS.md (RULE-10)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from .discovery import SourceFile


def _candidate_test_paths(source: SourceFile) -> list[Path]:
    """Generate candidate test file paths for a given source file.

    The mapping is intentionally lenient -- multiple naming conventions
    exist in the project, so we check several possible locations.

    Mapping patterns (for api layer, domain="kb", filename="service.py"):
        1. tests/unit/api/kb/test_kb_service.py
        2. tests/unit/api/kb/test_service.py
        3. tests/unit/api/test_kb_service.py  (top-level fallback)

    For nested modules (domain="token_limits", parent_domain="settings"):
        4. tests/unit/api/settings/test_token_limits_service.py
        5. tests/unit/api/settings/test_token_limits_{stem}.py

    Mapping patterns (for core layer, domain="wiki", filename="service.py"):
        1. tests/unit/core/wiki/test_service.py
        2. tests/unit/core/wiki/test_wiki_service.py
        3. tests/unit/core/test_wiki_service.py  (top-level fallback)
    """
    stem = source.path.stem  # e.g. "service" or "repository"
    domain = source.domain
    test_root = source.config.test_root

    # Build base test dir based on layer.
    layer_dir = test_root / source.layer

    candidates: list[Path] = []

    if source.layer == "api":
        domain_dir = layer_dir / domain
        # Pattern 1: tests/unit/api/{domain}/test_{domain}_{stem}.py
        candidates.append(domain_dir / f"test_{domain}_{stem}.py")
        # Pattern 2: tests/unit/api/{domain}/test_{stem}.py
        candidates.append(domain_dir / f"test_{stem}.py")
        # Pattern 3: tests/unit/api/test_{domain}_{stem}.py (top-level)
        candidates.append(layer_dir / f"test_{domain}_{stem}.py")
        # Pattern 4: tests/unit/api/{domain}/test_{domain}_{stem}_contract.py
        candidates.append(domain_dir / f"test_{domain}_{stem}_contract.py")
        candidates.append(layer_dir / f"test_{domain}_{stem}_contract.py")

        # For nested modules, also check the parent domain directory.
        if source.parent_domain:
            parent_dir = layer_dir / source.parent_domain
            # Pattern 5: tests/unit/api/{parent}/test_{domain}_{stem}.py
            candidates.append(parent_dir / f"test_{domain}_{stem}.py")
            # Pattern 6: tests/unit/api/{parent}/test_{domain}.py
            candidates.append(parent_dir / f"test_{domain}.py")
    else:
        domain_dir = layer_dir / domain
        # Pattern 1: tests/unit/core/{domain}/test_{stem}.py
        candidates.append(domain_dir / f"test_{stem}.py")
        # Pattern 2: tests/unit/core/{domain}/test_{domain}_{stem}.py
        candidates.append(domain_dir / f"test_{domain}_{stem}.py")
        # Pattern 3: tests/unit/core/test_{domain}_{stem}.py (top-level)
        candidates.append(layer_dir / f"test_{domain}_{stem}.py")

    return candidates


def _scan_domain_dir(
    domain_dir: Path,
    domain: str,
    stem: str,
) -> list[Path]:
    """Scan a domain test directory for files related to a source file.

    Matches files whose name contains the source stem (e.g. ``service``)
    or follows the ``test_{domain}_{stem}`` pattern.  This catches split
    test suites where tests live in ``test_{domain}_content.py``,
    ``test_{domain}_crud.py``, etc.

    When the source file has a generic name like ``service.py`` or
    ``repository.py``, also matches any ``test_{domain}_*.py`` file in
    the directory -- those files test aspects of the same domain service.
    """
    matches: list[Path] = []
    if not domain_dir.exists():
        return matches

    # Singular form of domain for test file naming conventions.
    # e.g. "chapters" -> "chapter", "novels" -> "novel"
    domain_singular = domain.rstrip("s") if domain.endswith("s") else domain

    for test_file in domain_dir.glob("test_*.py"):
        # Exact match: test_{stem}.py or test_{domain}_{stem}.py
        if test_file.name in {
            f"test_{stem}.py",
            f"test_{domain}_{stem}.py",
        }:
            matches.append(test_file)
            continue
        # Partial match: test file name contains the source stem.
        if stem in test_file.stem:
            matches.append(test_file)
            continue
        # Domain-level match: for generic source files (service.py,
        # repository.py), also match test_{domain_singular}_*.py files.
        if stem in {"service", "repository"} and test_file.stem.startswith(
            f"test_{domain_singular}_"
        ):
            matches.append(test_file)

    return matches


def _scan_parent_domain_dir(
    parent_dir: Path,
    leaf_domain: str,
) -> list[Path]:
    """Scan the parent domain test directory for nested module tests.

    Only matches files containing the leaf domain name.
    e.g. for leaf_domain="token_limits", matches test_token_limits_*.py.
    """
    matches: list[Path] = []
    if not parent_dir.exists():
        return matches

    prefix = f"test_{leaf_domain}_"

    for test_file in parent_dir.glob("test_*.py"):
        if test_file.stem.startswith(prefix):
            matches.append(test_file)

    return matches


def find_test_files(source: SourceFile) -> list[Path]:
    """Find existing test files matching the source file.

    Strategy:
    1. Check candidate paths (conventional naming patterns).
    2. Scan the domain test directory for partial name matches.
    3. For nested modules, also scan the parent domain directory.
    4. Combine all found files.
    """
    candidates = _candidate_test_paths(source)
    existing: list[Path] = [p for p in candidates if p.exists()]

    # Always scan the domain directory for additional related test files.
    test_root = source.config.test_root
    layer_dir = test_root / source.layer
    domain_dir = layer_dir / source.domain

    extra = _scan_domain_dir(
        domain_dir,
        domain=source.domain,
        stem=source.path.stem,
    )

    # For nested modules, also scan the parent domain directory.
    parent_extra: list[Path] = []
    if source.parent_domain:
        parent_dir = layer_dir / source.parent_domain
        parent_extra = _scan_parent_domain_dir(
            parent_dir,
            leaf_domain=source.domain,
        )

    # Merge without duplicates.
    all_files = set(existing) | set(extra) | set(parent_extra)
    return sorted(all_files)
