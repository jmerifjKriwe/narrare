"""RULE-I18N · i18n parity checks for bundled prompts.

Verifies:
- Every EN prompt file has DE and FR counterparts
- Reports counts of missing variants per language

Exits: called from ``prompt_integrity.run_all_checks()``.
"""

from __future__ import annotations

from pathlib import Path

from scripts.architecture.helpers import ROOT, relative_to_root
from scripts.architecture.types import CheckResult, Violation

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Categories / sub-paths to skip for i18n checks
_I18N_SKIP_CATEGORIES: frozenset[str] = frozenset({"meta"})

_I18N_SKIP_SUBPATHS: frozenset[str] = frozenset(
    {
        "writing/tones/",  # language-neutral tone labels
        "generation/name-styles/",  # language-neutral name style lists
    }
)

_I18N_SKIP_FILES: frozenset[str] = frozenset(
    {
        "system.lite.md",  # EN-only documented
    }
)

_REQUIRED_LANGS: tuple[str, ...] = ("de", "fr")

# ---------------------------------------------------------------------------
# i18n parity check — EN prompts need DE/FR
# ---------------------------------------------------------------------------


def check_i18n_parity(result: CheckResult) -> None:
    """Verify every EN prompt mode has DE and FR variants.

    Walks bundled prompt directories and reports missing DE/FR variants
    for every EN prompt file found (excluding skip-listed categories,
    sub-paths, and files).
    """
    bundled_dir = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    if not bundled_dir.is_dir():
        return

    en_missing_de: list[str] = []
    en_missing_fr: list[str] = []

    for en_file in bundled_dir.rglob("*.md"):
        parts = en_file.relative_to(bundled_dir).parts
        if "en" not in parts:
            continue

        try:
            lang_idx = parts.index("en")
        except ValueError:
            continue

        if lang_idx < 1 or lang_idx >= len(parts) - 1:
            continue

        category = parts[0]

        # Skip meta category
        if category in _I18N_SKIP_CATEGORIES:
            continue

        # Skip specific sub-paths
        rel_path_str = str(Path(*parts[:lang_idx])) + "/"
        if any(skip in rel_path_str for skip in _I18N_SKIP_SUBPATHS):
            continue

        # Skip EN-only documented files
        if parts[-1] in _I18N_SKIP_FILES:
            continue

        # Check DE
        de_parts = list(parts)
        de_parts[lang_idx] = "de"
        if not (bundled_dir / Path(*de_parts)).exists():
            en_missing_de.append(str(Path(*parts)))

        # Check FR
        fr_parts = list(parts)
        fr_parts[lang_idx] = "fr"
        if not (bundled_dir / Path(*fr_parts)).exists():
            en_missing_fr.append(str(Path(*parts)))

    if en_missing_de:
        result.approved_exceptions.append(
            Violation(
                file=Path("prompts/_bundled"),
                line=0,
                rule="PROMPT-INTEGRITY",
                detail=(
                    f"i18n parity: {len(en_missing_de)} EN prompt(s) missing DE variant. "
                    f"First 5: {', '.join(en_missing_de[:5])}"
                ),
                approved=True,
                approval_reason="i18n parity audit (D5.2)",
            )
        )

    if en_missing_fr:
        result.approved_exceptions.append(
            Violation(
                file=Path("prompts/_bundled"),
                line=0,
                rule="PROMPT-INTEGRITY",
                detail=(
                    f"i18n parity: {len(en_missing_fr)} EN prompt(s) missing FR variant. "
                    f"First 5: {', '.join(en_missing_fr[:5])}"
                ),
                approved=True,
                approval_reason="i18n parity audit (D5.2)",
            )
        )


def check_prompt_i18n_completeness(result: CheckResult) -> None:
    """Scan bundled prompt directories for i18n gaps.

    For each EN prompt file, checks that corresponding DE and FR files exist.
    Skips: meta category, writing/tones/, generation/name-styles/,
    system.lite.md (EN-only documented).
    """
    bundled_dir = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    if not bundled_dir.is_dir():
        return

    # Walk all EN files across all categories
    for en_file in bundled_dir.rglob("*.md"):
        # Only process EN files
        parts = en_file.relative_to(bundled_dir).parts
        if "en" not in parts:
            continue

        # Find the language position in path
        try:
            lang_idx = parts.index("en")
        except ValueError:
            continue

        # Skip: only process files directly under a language dir
        # e.g. category/en/mode/file.md
        if lang_idx < 1 or lang_idx >= len(parts) - 1:
            continue

        category = parts[0]

        # Skip meta category
        if category in _I18N_SKIP_CATEGORIES:
            continue

        # Skip specific sub-paths
        rel_path_str = str(Path(*parts[:lang_idx])) + "/"
        if any(skip in rel_path_str for skip in _I18N_SKIP_SUBPATHS):
            continue

        # Skip EN-only documented files
        if parts[-1] in _I18N_SKIP_FILES:
            continue

        # Check each required language
        for lang in _REQUIRED_LANGS:
            lang_parts = list(parts)
            lang_parts[lang_idx] = lang
            lang_file = bundled_dir / Path(*lang_parts)

            if not lang_file.exists():
                rel_path = relative_to_root(en_file)
                result.files_checked += 1
                result.approved_exceptions.append(
                    Violation(
                        file=Path(rel_path),
                        line=0,
                        rule="PROMPT-INTEGRITY",
                        detail=(
                            f"EN prompt exists but {lang.upper()} counterpart "
                            f"missing: {Path(*lang_parts)}"
                        ),
                        approved=True,
                        approval_reason=("i18n migration pending (CR-AUFG-04-07/04-10)"),
                    )
                )
