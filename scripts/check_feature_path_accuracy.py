#!/usr/bin/env python3
"""Feature-File Path Accuracy Checker.

Validates that implementation paths declared in feature-file frontmatter
(`service:`, `contract:`, `router:`, `prompt:`) actually exist on disk —
or are explicitly marked as planned/empty.

This checker prevents the "Dokumentiert ≠ Implementiert" drift class
(RC8 / AUFG-03-03): feature files that reference phantom paths in legacy
schemas (e.g. `apps/api/routers/...`) mislead readers and undermine the
SSOT contract between docs and code.

Rules
-----
For each feature file under `docs/features/`:

1. Parse YAML frontmatter (between `---` fences).
2. For each path-bearing field (`service`, `contract`, `router`, `prompt`):
   - Skip if empty (`""`), `~`, or `null` — explicit "not set".
   - Skip if the feature `status` is `planned` AND the field is empty —
     planned features are allowed to omit paths.
   - Skip shorthand paths that don't start with a known root prefix
     (`apps/`, `packages/`, `tools/`, `core/`, `scripts/`) — these are
     documented domain-shorthand and validated separately.
   - Strip `#anchor` suffixes and brace-expansion (`{a,b}`).
   - Split comma-separated multi-paths.
   - For each remaining absolute path: if it does NOT exist on disk → FAIL.

Exit codes
----------
    0 — all paths valid (or appropriately empty/planned).
    1 — at least one phantom path detected.

See: AUFG-03-03, RC8 in
     `_audit/results/technical-review/review-03-ai-features.md`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
FEATURES_DIR = ROOT / "docs" / "features"

# Fields that declare filesystem paths.
PATH_FIELDS: tuple[str, ...] = ("service", "contract", "router", "prompt")

# Path roots that are absolute from repo root and must exist.
# Note: `core/` alone is shorthand for `packages/core/narrare_core/` and is
# NOT treated as absolute — too many feature files use the shorthand.
ABSOLUTE_PREFIXES: tuple[str, ...] = (
    "apps/",
    "packages/",
    "tools/",
    "scripts/",
)

# Statuses where empty paths are expected and not flagged.
PLANNED_STATUSES: frozenset[str] = frozenset({"planned", "idea"})

# Statuses / markers indicating the feature is no longer active; paths in
# such files are historical and not enforced.
DEPRECATED_STATUSES: frozenset[str] = frozenset({"deprecated"})

# Anchor / brace-expansion / class-suffix patterns to strip before check.
_ANCHOR_RE = re.compile(r"#.*$")
_BRACE_RE = re.compile(r"\{[^}]*\}")
# Strip trailing " (ClassName)" or " (Class1, Class2)" annotations.
_CLASS_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")


@dataclass(frozen=True, slots=True)
class PathViolation:
    """A single phantom path declaration."""

    feature_file: Path
    field: str
    raw_path: str
    reason: str

    def format(self) -> str:
        rel = (
            self.feature_file.relative_to(ROOT)
            if self.feature_file.is_absolute()
            else self.feature_file
        )
        return f"  {rel} :: {self.field}={self.raw_path!r}\n    → {self.reason}"


def _extract_frontmatter(text: str) -> dict[str, Any] | None:
    """Return the parsed YAML frontmatter dict, or None if not present."""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    body = parts[1]
    try:
        data: Any = yaml.safe_load(body)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    # `data` is Any-typed from yaml; rebuild as dict[str, Any] so the return
    # type is fully known and callers can index by string keys safely.
    raw_dict: dict[Any, Any] = data  # type: ignore[assignment]
    return {str(key): value for key, value in raw_dict.items()}


def _split_paths(raw: str) -> list[str]:
    """Split a comma-separated path field into individual path strings.

    Comma-splits respect brace-expansion: commas inside `{...}` belong to the
    brace options and must not split the surrounding path.
    """
    if not raw:
        return []
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in raw:
        if ch == "{":
            depth += 1
            buf.append(ch)
        elif ch == "}":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == "," and depth == 0:
            piece = "".join(buf).strip()
            if piece:
                parts.append(piece)
            buf = []
        else:
            buf.append(ch)
    piece = "".join(buf).strip()
    if piece:
        parts.append(piece)
    return parts


def _normalize_for_check(path_str: str) -> str:
    """Strip anchors, class suffixes; resolve brace-expansion to first variant.

    Brace expansion like `{en,de,fr}` is replaced by its first option (`en`)
    rather than empty, so the resulting path is a representative concrete
    file that must exist on disk.
    """
    no_class = _CLASS_SUFFIX_RE.sub("", path_str)
    no_anchor = _ANCHOR_RE.sub("", no_class)

    def _first_variant(match: re.Match[str]) -> str:
        inner = match.group(0)[1:-1]
        options = [o.strip() for o in inner.split(",") if o.strip()]
        return options[0] if options else ""

    resolved = _BRACE_RE.sub(_first_variant, no_anchor)
    # Collapse any accidental double slashes from empty variants.
    resolved = re.sub(r"//+", "/", resolved)
    return resolved.strip()


def _is_absolute_path(path_str: str) -> bool:
    """True if the path starts with a known repo-root prefix."""
    return any(path_str.startswith(prefix) for prefix in ABSOLUTE_PREFIXES)


def _is_empty_marker(value: Any) -> bool:
    """True for explicit empty markers (`""`, `~`, `None`)."""
    if value is None:
        return True
    return isinstance(value, str) and value.strip() in {"", "~"}


def check_feature_file(path: Path) -> list[PathViolation]:
    """Return all phantom-path violations for a single feature file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    frontmatter = _extract_frontmatter(text)
    if frontmatter is None:
        return []

    status = str(frontmatter.get("status", "")).strip().lower()
    is_planned = status in PLANNED_STATUSES
    is_deprecated = status in DEPRECATED_STATUSES or "merged_into" in frontmatter
    if is_deprecated:
        return []

    violations: list[PathViolation] = []

    for field in PATH_FIELDS:
        value = frontmatter.get(field)
        if _is_empty_marker(value):
            # Empty is always acceptable; planned features are expected to be empty.
            continue

        if not isinstance(value, str):
            # Non-string (e.g. list) — out of scope for path validation.
            continue

        for raw_path in _split_paths(value):
            if not _is_absolute_path(raw_path):
                # Shorthand / domain-relative path — not validated here.
                continue

            normalized = _normalize_for_check(raw_path)
            target = ROOT / normalized

            if target.exists():
                continue

            # Path is absolute-form but missing on disk.
            if is_planned:
                reason = (
                    f"path does not exist and feature is {status!r}; "
                    "leave the field empty until implementation lands"
                )
            else:
                reason = "path does not exist on disk (legacy schema or phantom?)"
            violations.append(
                PathViolation(
                    feature_file=path,
                    field=field,
                    raw_path=raw_path,
                    reason=reason,
                )
            )

    return violations


def collect_violations(features_dir: Path = FEATURES_DIR) -> list[PathViolation]:
    """Walk `features_dir` and return all violations across feature files."""
    if not features_dir.is_dir():
        return []
    violations: list[PathViolation] = []
    for md_file in sorted(features_dir.rglob("*.md")):
        violations.extend(check_feature_file(md_file))
    return violations


def main(argv: list[str] | None = None) -> int:
    """Run the checker; return 0 if clean, 1 if phantom paths are found."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate feature-file frontmatter paths against the filesystem.",
    )
    parser.add_argument(
        "--features-dir",
        type=Path,
        default=FEATURES_DIR,
        help="Feature directory to scan (default: docs/features).",
    )
    args = parser.parse_args(argv)

    features_dir: Path = args.features_dir
    if not features_dir.is_absolute():
        features_dir = ROOT / features_dir

    print("Feature-File Path Accuracy Check")
    print("=" * 60)
    print(f"Scanning: {features_dir.relative_to(ROOT)}")
    print("-" * 60)

    violations = collect_violations(features_dir)

    if not violations:
        print("✅ All feature-file frontmatter paths are accurate.")
        return 0

    print(f"❌ {len(violations)} phantom path(s) detected:")
    for v in violations:
        print(v.format())
    print("-" * 60)
    print(
        'Fix: either remove the path, set it to empty ("") for planned '
        "features,\nor create the referenced file. Phantom paths undermine "
        "the SSOT contract."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
