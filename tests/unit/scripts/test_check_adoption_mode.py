"""Mode-level adoption tests (ADR-039) — resolution and runtime.

Tests for mode override resolution and runtime requirements checking.
Score computation, aggregation, and output tests are in
test_check_adoption_mode_score.py.
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

from typing import Any  # noqa: E402

from adoption.scorer import compute_adoption_report  # noqa: E402
from adoption.scorer_modes import (  # noqa: E402
    _check_runtime_requirements,
    compute_mode_score,
)
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


def _minimal_registry_v2(
    *,
    modes: dict[str, dict[str, Any]] | None = None,
    must: list[str] | None = None,
    should: list[str] | None = None,
    infra: dict[str, str] | None = None,
    cat_runtime: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a minimal v2.0.0 registry with mode overrides."""
    return {
        "version": "2.0.0",
        "category_defaults": (
            {"writing": {"runtime_requirements": cat_runtime}} if cat_runtime else {}
        ),
        "features": {
            "writing": {
                "modes": modes or {"new_chapter": {}},
                "required_infrastructure": infra
                or {
                    "prompt_composer": "required",
                    "meta_prompt": "required",
                    "i18n": "partial",
                },
                "context_variables": {
                    "must": must or ["user_preferences"],
                    "should": should or [],
                },
            }
        },
        "inline_fallbacks": [],
    }


# ── Mode override resolution ───────────────────────────────────────


class TestModeOverrideResolution:
    """Verify mode-level overrides of category defaults."""

    def test_mode_inherits_category_defaults(self) -> None:
        """Mode with no overrides inherits category-level runtime defaults."""
        registry = _minimal_registry_v2(
            cat_runtime={"preference_enrichment": "required"},
        )
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        mode = report.categories[0].modes[0]
        assert mode.mode == "new_chapter"
        rt = next(d for d in mode.runtime_details if d.requirement == "preference_enrichment")
        assert rt.declared == "required"
        assert rt.evidence_status == "missing"

    def test_inline_suggest_overrides_budget(self) -> None:
        """Mode overrides change runtime requirements from the category defaults."""
        registry = _minimal_registry_v2(
            cat_runtime={
                "kb_suggested": "provided",
                "budget_resolution": "required",
            },
            modes={
                "inline_suggest": {
                    "overrides": {
                        "runtime_requirements": {
                            "kb_suggested": "budget_rejected",
                            "budget_resolution": "none",
                        },
                    },
                },
            },
        )
        prompts = [_make_prompt("writing", "en", "inline_suggest", {"user_preferences"})]
        report = compute_adoption_report(registry, prompts)
        mode = report.categories[0].modes[0]

        kb = next(d for d in mode.runtime_details if d.requirement == "kb_suggested")
        assert kb.declared == "budget_rejected"
        assert kb.evidence_status == "missing"

        br = next(d for d in mode.runtime_details if d.requirement == "budget_resolution")
        assert br.declared == "none"
        assert br.evidence_status == "verified"

    def test_co_author_overrides_must_vars(self) -> None:
        """Mode context_variable overrides extend must/should vars."""
        registry = _minimal_registry_v2(
            must=["user_preferences"],
            modes={
                "co_author": {
                    "overrides": {
                        "context_variables": {
                            "must": ["user_preferences", "avoidance_patterns"],
                            "should": ["kb_suggested"],
                        },
                    },
                },
            },
        )
        prompts = [
            _make_prompt("writing", "en", "co_author", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        mode = report.categories[0].modes[0]
        assert mode.mode == "co_author"
        # avoidance_patterns is missing → score < 1.0
        assert mode.score < 1.0

    def test_unknown_mode_gets_category_defaults(self) -> None:
        """A mode without overrides uses category-level infrastructure and vars."""
        registry = _minimal_registry_v2(modes={"new_chapter": {}})
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        mode = report.categories[0].modes[0]
        assert mode.mode == "new_chapter"
        # Empty runtime_reqs → runtime_verified=False
        assert mode.runtime_verified is False

    def test_backward_compat_string_mode(self) -> None:
        """Old list-of-strings mode format resolves correctly."""
        registry = _minimal_registry_v2()
        # Switch to old list format
        reg: dict[str, Any] = registry
        reg["features"]["writing"]["modes"] = ["new_chapter"]
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        assert len(report.categories[0].modes) == 1
        assert report.categories[0].modes[0].mode == "new_chapter"


# ── Runtime requirements checking ──────────────────────────────────


class TestRuntimeRequirements:
    """Verify _check_runtime_requirements and compute_mode_score runtime logic."""

    def test_all_required_passes_for_none_defaults(self) -> None:
        """'none', 'optional', and 'provided' count as verified."""
        details, verified = _check_runtime_requirements(
            {
                "a": "none",
                "b": "optional",
                "c": "provided",
            }
        )
        assert verified is True
        assert len(details) == 3
        for d in details:
            assert d.evidence_status == "verified"

    def test_required_field_marked_missing(self) -> None:
        """'required' produces evidence_status 'missing' and blocks verified."""
        details, verified = _check_runtime_requirements({"feature_a": "required"})
        assert verified is False
        assert details[0].evidence_status == "missing"
        assert details[0].declared == "required"
        assert details[0].requirement == "feature_a"

    def test_mode_with_all_runtime_verified(self) -> None:
        """compute_mode_score with all-passing runtime_reqs → runtime_verified=True."""
        ms = compute_mode_score(
            mode_name="test",
            must_vars=["v1"],
            should_vars=[],
            infra={},
            runtime_reqs={"a": "none", "b": "provided"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
        )
        assert ms.runtime_verified is True

    def test_mode_not_adopted_when_static_fails(self) -> None:
        """Mode with low static score has adopted=False."""
        ms = compute_mode_score(
            mode_name="test",
            must_vars=["v1", "v2"],
            should_vars=[],
            infra={},
            runtime_reqs={},
            all_vars=set(),
            i18n_frac=0.0,
            has_prompts=False,
            fb_count=0,
        )
        assert ms.static_verified is False
        assert ms.adopted is False

    def test_mode_not_adopted_when_runtime_fails(self) -> None:
        """Mode with perfect static but failing runtime → adopted=False."""
        ms = compute_mode_score(
            mode_name="test",
            must_vars=["v1"],
            should_vars=[],
            infra={"prompt_composer": "required"},
            runtime_reqs={"a": "required"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
        )
        assert ms.static_verified is True
        assert ms.runtime_verified is False
        assert ms.adopted is False

    def test_runtime_checkdetail_has_correct_fields(self) -> None:
        """RuntimeCheckDetail has all four fields populated."""
        details, _ = _check_runtime_requirements({"feature_x": "required"})
        assert len(details) == 1
        d = details[0]
        assert d.requirement == "feature_x"
        assert d.declared == "required"
        assert d.evidence_status == "missing"
        assert isinstance(d.note, str)
        assert len(d.note) > 0
