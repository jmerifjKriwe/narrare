"""Mode score computation and aggregation tests (ADR-039).

Tests for ModeScore computation and aggregation into AdoptionReport.

Output formatting and backward compatibility tests are in
test_check_adoption_mode_output.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from adoption.scorer import compute_adoption_report  # noqa: E402
from adoption.scorer_modes import (  # noqa: E402
    ModeScore,
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


# ── ModeScore computation ──────────────────────────────────────────


class TestModeScoreComputation:
    """Verify ModeScore dataclass and compute_mode_score()."""

    def test_mode_score_from_perfect_prompts(self) -> None:
        """All vars present, all runtime pass → score 1.0, PASS, adopted."""
        ms = compute_mode_score(
            mode_name="perfect",
            must_vars=["v1", "v2"],
            should_vars=["s1"],
            infra={"prompt_composer": "required", "i18n": "partial"},
            runtime_reqs={"a": "none", "b": "provided"},
            all_vars={"v1", "v2", "s1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
        )
        assert ms.score == 1.0
        assert ms.status == "PASS"
        assert ms.static_verified is True
        assert ms.runtime_verified is True
        assert ms.adopted is True

    def test_mode_score_with_missing_vars(self) -> None:
        """Missing must vars reduce score below PASS_THRESHOLD."""
        ms = compute_mode_score(
            mode_name="missing",
            must_vars=["v1", "v2", "v3"],
            should_vars=[],
            infra={"prompt_composer": "required"},
            runtime_reqs={},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
        )
        # Score: must (1/3 * 1.0) + infra (1.0 * 1.0) / denom (3.0 + 1.0) = 0.5
        assert ms.score == 0.5
        assert ms.status == "FAIL"
        assert ms.static_verified is False

    def test_mode_score_with_inline_overrides(self) -> None:
        """Mode score respects resolved must/should/infra."""
        ms = compute_mode_score(
            mode_name="override",
            must_vars=["v1", "v2"],
            should_vars=["s1"],
            infra={"prompt_composer": "required", "i18n": "partial"},
            runtime_reqs={},
            all_vars={"v1", "v2", "s1"},
            i18n_frac=0.5,
            has_prompts=True,
            fb_count=0,
        )
        # must: 2/2*1.0 + should: 1/1*0.3 + pc: 1.0*1.0 + i18n: 0.5*0.5
        # numerator: 1.0+0.3+1.0+0.25=2.55 / denom: 2.0+0.3+1.0+0.5=3.8
        assert 0.93 < ms.score < 0.94

    def test_mode_static_verified_requires_pass_score(self) -> None:
        """static_verified is True iff score >= PASS_THRESHOLD."""
        high = compute_mode_score(
            mode_name="high",
            must_vars=["v1"],
            should_vars=[],
            infra={"prompt_composer": "required"},
            runtime_reqs={},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
        )
        assert high.static_verified is True

        low = compute_mode_score(
            mode_name="low",
            must_vars=["v1"],
            should_vars=[],
            infra={"prompt_composer": "required"},
            runtime_reqs={},
            all_vars=set(),
            i18n_frac=0.0,
            has_prompts=False,
            fb_count=0,
        )
        assert low.static_verified is False

    def test_mode_runtime_verified_requires_all_required_pass(self) -> None:
        """runtime_verified is True only when all runtime requirements pass."""
        mp = compute_mode_score(
            mode_name="pass",
            must_vars=["v1"],
            should_vars=[],
            infra={},
            runtime_reqs={"a": "none", "b": "optional", "c": "provided"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
        )
        assert mp.runtime_verified is True

        mf = compute_mode_score(
            mode_name="fail",
            must_vars=["v1"],
            should_vars=[],
            infra={},
            runtime_reqs={"a": "required"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
        )
        assert mf.runtime_verified is False

    def test_mode_adopted_requires_both_verified(self) -> None:
        """adopted = static_verified AND runtime_verified."""
        mp = compute_mode_score(
            mode_name="both_pass",
            must_vars=["v1"],
            should_vars=[],
            infra={},
            runtime_reqs={"a": "none"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
        )
        assert mp.static_verified is True
        assert mp.runtime_verified is True
        assert mp.adopted is True

        ms = compute_mode_score(
            mode_name="static_fail",
            must_vars=["v1"],
            should_vars=[],
            infra={},
            runtime_reqs={"a": "none"},
            all_vars=set(),
            i18n_frac=0.0,
            has_prompts=False,
            fb_count=0,
        )
        assert ms.adopted is False

        mr = compute_mode_score(
            mode_name="rt_fail",
            must_vars=["v1"],
            should_vars=[],
            infra={},
            runtime_reqs={"a": "required"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
        )
        assert mr.adopted is False


# ── ModeScore aggregation ──────────────────────────────────────────


class TestModeScoreAggregation:
    """Verify mode scores aggregated into AdoptionReport via compute_adoption_report."""

    def test_report_has_mode_count(self) -> None:
        """report.mode_count reflects total modes across categories."""
        registry = _minimal_registry_v2(
            modes={"new_chapter": {}, "inline_suggest": {}},
        )
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
            _make_prompt("writing", "en", "inline_suggest", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        assert report.mode_count == 2

    def test_report_counts_runtime_verified(self) -> None:
        """report.runtime_verified_count counts modes with all runtime passing."""
        registry = _minimal_registry_v2(
            cat_runtime={"feature_a": "none", "feature_b": "provided"},
            modes={"new_chapter": {}, "inline_suggest": {}},
        )
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        assert report.runtime_verified_count == 2

    def test_report_counts_adopted(self) -> None:
        """report.adopted_count counts modes that are both verified."""
        registry = _minimal_registry_v2(
            cat_runtime={"feature_a": "none"},
            modes={"new_chapter": {}, "inline_suggest": {}},
        )
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
            _make_prompt("writing", "en", "inline_suggest", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        assert report.adopted_count == 2

    def test_category_has_modes_list(self) -> None:
        """CategoryScore.modes is populated with ModeScore instances."""
        registry = _minimal_registry_v2()
        prompts = [_make_prompt("writing", "en", "new_chapter", {"user_preferences"})]
        report = compute_adoption_report(registry, prompts)
        cat = report.categories[0]
        assert isinstance(cat.modes, list)
        assert len(cat.modes) == 1
        assert isinstance(cat.modes[0], ModeScore)


# ── requires_runtime_evidence gating (ADR-040 Decision 4) ───────────


class TestRequiresRuntimeEvidenceGating:
    """Verify requires_runtime_evidence flag gates the adopted state."""

    def test_runtime_evidence_required_blocks_adopted_without_runtime(self) -> None:
        """requires_runtime_evidence=True forces adopted=False when not runtime verified."""
        ms = compute_mode_score(
            mode_name="gated",
            must_vars=["v1"],
            should_vars=[],
            infra={"prompt_composer": "required"},
            runtime_reqs={"a": "required"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
            requires_runtime_evidence=True,
        )
        assert ms.static_verified is True
        assert ms.runtime_verified is False
        assert ms.requires_runtime_evidence is True
        assert ms.adopted is False

    def test_runtime_evidence_required_allows_adopted_with_runtime(self) -> None:
        """requires_runtime_evidence=True allows adopted when both verified."""
        ms = compute_mode_score(
            mode_name="both_pass",
            must_vars=["v1"],
            should_vars=[],
            infra={"prompt_composer": "required"},
            runtime_reqs={"a": "none"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
            requires_runtime_evidence=True,
        )
        assert ms.static_verified is True
        assert ms.runtime_verified is True
        assert ms.adopted is True

    def test_runtime_evidence_not_required_adopted_from_static_only(self) -> None:
        """requires_runtime_evidence=False allows adopted from static only."""
        ms = compute_mode_score(
            mode_name="deferred",
            must_vars=["v1"],
            should_vars=[],
            infra={"prompt_composer": "required"},
            runtime_reqs={"a": "required"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
            requires_runtime_evidence=False,
        )
        assert ms.static_verified is True
        assert ms.runtime_verified is False
        assert ms.requires_runtime_evidence is False
        assert ms.adopted is True

    def test_runtime_evidence_not_required_static_fail_still_unadopted(self) -> None:
        """requires_runtime_evidence=False still requires static_verified."""
        ms = compute_mode_score(
            mode_name="bad_static",
            must_vars=["v1", "v2", "v3"],
            should_vars=[],
            infra={},
            runtime_reqs={"a": "required"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=False,
            fb_count=0,
            requires_runtime_evidence=False,
        )
        assert ms.static_verified is False
        assert ms.adopted is False

    def test_mode_config_flag_flows_through_report(self) -> None:
        """requires_runtime_evidence from registry config flows to ModeScore."""
        registry = _minimal_registry_v2(
            modes={
                "gated": {"requires_runtime_evidence": True},
                "deferred": {"requires_runtime_evidence": False},
            },
            cat_runtime={"feature_a": "required"},
        )
        prompts = [
            _make_prompt("writing", "en", "gated", {"user_preferences"}),
            _make_prompt("writing", "en", "deferred", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        cat = report.categories[0]
        gated = next(m for m in cat.modes if m.mode == "gated")
        deferred = next(m for m in cat.modes if m.mode == "deferred")
        assert gated.requires_runtime_evidence is True
        assert gated.adopted is False
        assert deferred.requires_runtime_evidence is False
        assert deferred.adopted is True
