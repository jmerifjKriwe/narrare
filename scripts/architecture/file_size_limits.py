"""RULE-04 file-size classification and limits — the single SSOT.

Both RULE-04 gates consume this module, so they classify identically by
construction:

* ``scripts/architecture/_checkers/file_size.py`` — architecture-constraints
  pre-commit hook / CI architecture job (``check_architecture.py``)
* ``scripts/check_python_file_size.py`` — python-size ratchet gate
  (pre-commit hook ``python-size`` / ``just check-python-size``)

Historical defect (fixed 2026-08-19): the two gates carried separate
classification predicates and limit vocabularies that had drifted apart —
an overbroad ``startswith("router")`` router predicate, script/dependency
categories missing on the architecture side, repository/contracts/gateway/
composer categories missing on the python-size side, and a models
200-vs-500 value split. Two checkers asserting the same rule with
different truths is the defect; the fix is this single module.

Values SSOT: ``pyproject.toml [tool.narrare.architecture.file_size_limits]``
— the table must define a limit for every canonical category below
(validated; missing or stale keys fail loudly instead of silently falling
back to hardcoded defaults).

Classification authority (reconciliation, 2026-08-19). Reconciliation
records which side's predicate won — current values are read from the
pyproject SSOT table and deliberately not repeated here (an enumerated
copy would silently stale on the next value change):

* router — precise python-size predicate (``router.py`` / ``router_*.py``);
  ``routers.py`` / ``routering.py`` are general modules.
* dependency, script — python-size categories adopted.
* config_schema — python-size predicate (``config.py`` / ``schemas.py`` /
  ``settings.py`` / ``*_schemas.py``).
* models — CONSTRAINTS.md RULE-04 has no models row, so the pyproject
  table entry is the authority over the python-size gate's former 500.
* repository, contracts, gateway, composer — architecture-only categories
  retained (their stricter limits live in the pyproject table).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from typing import Any, cast

from scripts.architecture.helpers import load_config

# Canonical categories in classification priority order (first match wins).
# ``test`` outranks everything; the path-based ``script`` rule outranks
# name-based rules (e.g. scripts/test_assertion_audit/models.py is a script).
CATEGORY_ORDER: tuple[str, ...] = (
    "test",
    "script",
    "router",
    "dependency",
    "service",
    "agent",
    "config_schema",
    "models",
    "repository",
    "contracts",
    "gateway",
    "composer",
    "general",
)
CANONICAL_CATEGORIES: frozenset[str] = frozenset(CATEGORY_ORDER)


class FileSizeLimitsError(ValueError):
    """Raised when the file_size_limits SSOT table is invalid or incomplete."""


def validate_limits(table: Mapping[str, Any]) -> dict[str, int]:
    """Validate a limits table against the canonical category vocabulary.

    Rejects missing keys (silent-fallback risk) and stale/unknown keys
    (vocabulary drift), and non-positive / non-integer values.
    """
    keys = set(table.keys())
    missing = sorted(CANONICAL_CATEGORIES - keys)
    unknown = sorted(keys - CANONICAL_CATEGORIES)
    if missing or unknown:
        parts: list[str] = []
        if missing:
            parts.append(f"missing categories: {', '.join(missing)}")
        if unknown:
            parts.append(f"unknown/stale categories: {', '.join(unknown)}")
        msg = f"file_size_limits table invalid ({'; '.join(parts)})"
        raise FileSizeLimitsError(msg)

    limits: dict[str, int] = {}
    for category in CATEGORY_ORDER:
        value = table[category]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            msg = (
                f"file_size_limits: limit for {category!r} must be a positive "
                f"integer, got {value!r}"
            )
            raise FileSizeLimitsError(msg)
        limits[category] = value
    return limits


@lru_cache(maxsize=1)
def load_limits() -> dict[str, int]:
    """Load and validate the limits table from pyproject.toml (values SSOT)."""
    config = load_config()
    raw: Any = config.get("file_size_limits", {})
    if not isinstance(raw, Mapping):
        msg = "file_size_limits table must be a TOML table of category = limit"
        raise FileSizeLimitsError(msg)
    return validate_limits(cast("Mapping[str, Any]", raw))


def classify(
    rel_path: str,
    limits: Mapping[str, int] | None = None,
) -> tuple[str, int]:
    """Classify a Python file and return ``(category, hard_line_limit)``.

    Args:
        rel_path: Project-root-relative POSIX path of the file.
        limits: Optional limits-table override (e.g. tests). ``None`` (or an
            empty mapping) loads the validated pyproject SSOT table. Partial
            or stale tables raise :class:`FileSizeLimitsError` — there are no
            per-key fallbacks, because fallback defaults are how the two
            gates originally drifted apart.
    """
    table = load_limits() if not limits else validate_limits(limits)
    name = rel_path.rsplit("/", 1)[-1]

    # 1. Test files: test_*.py — first-match priority over all name rules.
    if name.startswith("test_") and name.endswith(".py"):
        return "test", table["test"]

    # 2. Scripts directory (tooling is inherently longer).
    if rel_path.startswith("scripts/"):
        return "script", table["script"]

    # 3. Router files: router.py, router_*.py (NOT routers.py/routering.py).
    if name == "router.py" or name.startswith("router_"):
        return "router", table["router"]

    # 4. Dependency files: dependencies.py, deps.py, deps_*.py.
    if name in ("dependencies.py", "deps.py") or name.startswith("deps_"):
        return "dependency", table["dependency"]

    # 5. Service files: service.py, *_service.py.
    if name == "service.py" or name.endswith("_service.py"):
        return "service", table["service"]

    # 6. Agent files: agent.py, *_agent.py.
    if name == "agent.py" or name.endswith("_agent.py"):
        return "agent", table["agent"]

    # 7. Config/schema files: config.py, schemas.py, settings.py, *_schemas.py.
    if name in ("config.py", "schemas.py", "settings.py") or name.endswith("_schemas.py"):
        return "config_schema", table["config_schema"]

    # 8. Models: models.py (pyproject per-path entry is the value authority).
    if name == "models.py":
        return "models", table["models"]

    # 9. Repository files: repository.py, *_repo.py.
    if name == "repository.py" or name.endswith("_repo.py"):
        return "repository", table["repository"]

    # 10. Contracts: contracts.py.
    if name == "contracts.py":
        return "contracts", table["contracts"]

    # 11. Gateway: gateway.py.
    if name == "gateway.py":
        return "gateway", table["gateway"]

    # 12. Composer: composer.py.
    if name == "composer.py":
        return "composer", table["composer"]

    # 13. Everything else.
    return "general", table["general"]
