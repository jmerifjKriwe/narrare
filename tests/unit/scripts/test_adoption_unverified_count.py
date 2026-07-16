"""Tests for AdoptionReport.unverified_count — false-positive proxy visibility.

Validates that infrastructure assumed from bundled-prompt file presence only
(``token_budget``, ``injection_defense``) is counted as unverified in the
adoption report, while verified branches (variable evidence, prompt_composer,
i18n) are not.

Extracted from ``test_check_adoption.py`` per RULE-04 (file-size limit).

See: scripts/adoption/scorer_checks.py fallback branch.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from adoption.scorer import compute_adoption_report  # noqa: E402
from prompt_checks import PromptFile  # noqa: E402

# ── Helpers ────────────────────────────────────────────────────────


def _make_prompt(
    category: str = "writing",
    locale: str = "en",
    mode: str = "",
    variables: set[str] | None = None,
) -> PromptFile:
    """Create a minimal PromptFile for testing."""
    return PromptFile(
        path=Path(f"_bundled/{category}/{locale}/{mode}/system.md"),
        rel_path=f"{category}/{locale}/{mode}/system.md",
        variables=variables or set(),
        category=category,
        locale=locale,
        mode=mode,
    )


def _minimal_registry(
    *,
    infra: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build a minimal registry with one category for testing."""
    return {
        "features": {
            "writing": {
                "modes": ["new_chapter"],
                "required_infrastructure": infra or {},
                "context_variables": {
                    "must": ["user_preferences"],
                    "should": [],
                },
            }
        },
        "inline_fallbacks": [],
    }


# ── unverified_count (false-positive proxy visibility) ─────────────


class TestUnverifiedCount:
    """Verify AdoptionReport.unverified_count surfaces file-presence-only assumptions."""

    def test_token_budget_counted_as_unverified(self) -> None:
        """token_budget with bundled prompts → unverified_count >= 1."""
        registry = _minimal_registry(
            infra={"token_budget": "required"},
        )
        prompts = [_make_prompt("writing", "en", "new_chapter")]
        report = compute_adoption_report(registry, prompts)
        assert report.unverified_count >= 1

    def test_injection_defense_counted_as_unverified(self) -> None:
        registry = _minimal_registry(
            infra={"injection_defense": "required"},
        )
        prompts = [_make_prompt("writing", "en", "new_chapter")]
        report = compute_adoption_report(registry, prompts)
        assert report.unverified_count >= 1

    def test_both_unverified_counted(self) -> None:
        registry = _minimal_registry(
            infra={"token_budget": "required", "injection_defense": "required"},
        )
        prompts = [_make_prompt("writing", "en", "new_chapter")]
        report = compute_adoption_report(registry, prompts)
        assert report.unverified_count >= 2

    def test_no_unverified_for_variable_evidence_infra(self) -> None:
        """kb_entities (variable evidence) → unverified_count == 0."""
        registry = _minimal_registry(
            infra={"kb_entities": "required"},
        )
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"kb_characters"}),
        ]
        report = compute_adoption_report(registry, prompts)
        assert report.unverified_count == 0

    def test_no_unverified_for_prompt_composer(self) -> None:
        """prompt_composer has its own branch → not unverified."""
        registry = _minimal_registry(
            infra={"prompt_composer": "required"},
        )
        prompts = [_make_prompt("writing", "en", "new_chapter")]
        report = compute_adoption_report(registry, prompts)
        assert report.unverified_count == 0

    def test_unverified_excluded_from_verified_score(self) -> None:
        """An unverified detail must NOT raise the verified score (RULE-18b).

        Invariant REVERSED from the old ratchet behaviour: a category whose
        only "adopted" item is unverified now scores 0 in the verified
        aggregate, because unverified infra is excluded from numerator AND
        denominator (Option A). Previously the file-presence proxy
        (``adopted=1.0``) inflated the score to match a verified item.
        """
        registry_unverified = _minimal_registry(
            infra={"token_budget": "required"},
        )
        registry_verified = _minimal_registry(
            infra={"kb_entities": "required"},
        )
        # must var is absent (no user_preferences in the prompt) → verified
        # must contributes 0. So the unverified registry's only "adopted" item
        # is token_budget, which is excluded → verified score 0.0. The verified
        # registry's kb_entities resolves (kb_characters present) → score > 0.
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"kb_characters"}),
        ]
        report_u = compute_adoption_report(registry_unverified, prompts)
        report_v = compute_adoption_report(registry_verified, prompts)
        # Unverified no longer inflates: verified score strictly exceeds it,
        # and the all-unverified category scores exactly 0.
        assert report_u.overall_score == 0.0
        assert report_v.overall_score > report_u.overall_score

    def test_unverified_never_enters_verified_aggregate(self) -> None:
        """Regression: unverified infra must never contribute to the verified score.

        A category with one verified must var (1 of 2 present → 1.0/2.0 = 0.5)
        plus an unverified infra (``adopted=1.0``) must score exactly 0.5. If
        the unverified item leaked back into the aggregate it would add
        weight 1.0 to numerator and denominator → 2.0/3.0 ≈ 0.67. This locks
        the Option-A exclusion at the category-score level.
        """
        registry = {
            "features": {
                "writing": {
                    "modes": ["new_chapter"],
                    "required_infrastructure": {"token_budget": "required"},
                    "context_variables": {
                        "must": ["present_var", "missing_var"],
                        "should": [],
                    },
                }
            },
            "inline_fallbacks": [],
        }
        prompts = [_make_prompt("writing", "en", "new_chapter", {"present_var"})]
        report = compute_adoption_report(registry, prompts)
        assert report.categories[0].score == 0.5
        # The unverified item is still surfaced in the report (not silenced).
        assert report.unverified_count == 1
