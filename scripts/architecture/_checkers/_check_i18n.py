"""RULE-I18N · i18n parity checks for bundled prompts.

Verifies:
- Localized-required prompt families have DE and FR counterparts
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

# Categories that require bundled DE/FR prompt variants under ADR-026 Phase 5.
_LOCALIZED_REQUIRED_CATEGORIES: frozenset[str] = frozenset({"meta", "universal", "universal_rules"})

_I18N_SKIP_SUBPATHS: frozenset[str] = frozenset(
    {
        "writing/tones/",  # language-neutral tone labels
        "generation/name-styles/",  # language-neutral name style lists
    }
)

_REQUIRED_LANGS: tuple[str, ...] = ("de", "fr")

# ---------------------------------------------------------------------------
# i18n parity check — localized-required EN prompts need DE/FR
# ---------------------------------------------------------------------------


def _is_localized_required_prompt(parts: tuple[str, ...]) -> bool:
    """Return True when a bundled EN prompt path requires DE/FR counterparts."""
    if "en" not in parts:
        return False

    try:
        lang_idx = parts.index("en")
    except ValueError:
        return False

    if lang_idx < 1 or lang_idx >= len(parts) - 1:
        return False

    category = parts[0]
    if category not in _LOCALIZED_REQUIRED_CATEGORIES:
        return False

    rel_path_str = str(Path(*parts[:lang_idx])) + "/"
    return not any(skip in rel_path_str for skip in _I18N_SKIP_SUBPATHS)


def check_i18n_parity(result: CheckResult) -> None:
    """Verify localized-required EN prompt modes have DE and FR variants.

    Bundled feature prompt templates are EN-only by default under ADR-026 Phase
    5. This check only reports missing bundled variants for prompt categories
    whose capability/persona/security wording remains localized-required.
    """
    bundled_dir = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    if not bundled_dir.is_dir():
        return

    en_missing_de: list[str] = []
    en_missing_fr: list[str] = []

    for en_file in bundled_dir.rglob("*.md"):
        parts = en_file.relative_to(bundled_dir).parts
        if not _is_localized_required_prompt(parts):
            continue
        lang_idx = parts.index("en")

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

    For each localized-required EN prompt file, checks that corresponding DE and
    FR files exist. Bundled feature prompt templates are EN-only by default; UI
    i18n strictness is enforced by separate frontend locale checks.
    """
    bundled_dir = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    if not bundled_dir.is_dir():
        return

    # Walk all EN files across all categories
    for en_file in bundled_dir.rglob("*.md"):
        parts = en_file.relative_to(bundled_dir).parts
        if not _is_localized_required_prompt(parts):
            continue
        lang_idx = parts.index("en")

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
