"""Tests for the adoption score computation.

Validates weighted score calculation, threshold classification,
and individual check dimensions.
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

from adoption.scorer import (  # noqa: E402
    PASS_THRESHOLD,
    WARN_THRESHOLD,
    _status,
    compute_adoption_report,
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


def _minimal_registry(
    *,
    must: list[str] | None = None,
    should: list[str] | None = None,
    infra: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build a minimal registry with one category for testing."""
    return {
        "features": {
            "writing": {
                "modes": ["new_chapter"],
                "required_infrastructure": infra
                or {
                    "prompt_composer": "required",
                    "meta_prompt": "required",
                    "i18n": "required",
                },
                "context_variables": {
                    "must": must or ["user_preferences"],
                    "should": should or [],
                },
            }
        },
        "inline_fallbacks": [],
    }


# ── _status ────────────────────────────────────────────────────────


class TestStatus:
    def test_pass(self) -> None:
        assert _status(0.90) == "PASS"
        assert _status(PASS_THRESHOLD) == "PASS"

    def test_warn(self) -> None:
        assert _status(0.75) == "WARN"
        assert _status(WARN_THRESHOLD) == "WARN"

    def test_fail(self) -> None:
        assert _status(0.50) == "FAIL"
        assert _status(0.0) == "FAIL"


# ── compute_adoption_report — perfect score ────────────────────────


class TestPerfectScore:
    def test_all_present_scores_100(self) -> None:
        registry = _minimal_registry(
            must=["user_preferences", "avoidance_patterns"],
        )
        prompts = [
            _make_prompt(
                "writing",
                "en",
                "new_chapter",
                {"user_preferences", "avoidance_patterns"},
            ),
            _make_prompt("writing", "de", "new_chapter"),
            _make_prompt("writing", "fr", "new_chapter"),
        ]
        report = compute_adoption_report(registry, prompts)
        assert report.overall_score == 1.0
        assert report.status == "PASS"
        assert len(report.categories) == 1
        assert report.categories[0].missing_must == []


# ── compute_adoption_report — missing must vars ────────────────────


class TestMissingMustVars:
    def test_missing_must_reduces_score(self) -> None:
        registry = _minimal_registry(
            must=["user_preferences", "avoidance_patterns", "kb_relationships"],
        )
        prompts = [
            _make_prompt(
                "writing",
                "en",
                "new_chapter",
                {"user_preferences"},  # missing 2 of 3 must vars
            ),
        ]
        report = compute_adoption_report(registry, prompts)
        cat = report.categories[0]
        assert "avoidance_patterns" in cat.missing_must
        assert "kb_relationships" in cat.missing_must
        assert cat.score < 1.0

    def test_zero_must_vars_present(self) -> None:
        registry = _minimal_registry(must=["a", "b", "c"])
        prompts = [_make_prompt("writing", "en", "new_chapter", set())]
        report = compute_adoption_report(registry, prompts)
        assert report.categories[0].score < WARN_THRESHOLD


# ── compute_adoption_report — should vars ──────────────────────────


class TestShouldVars:
    def test_missing_should_warns_not_fails(self) -> None:
        registry = _minimal_registry(
            must=["user_preferences"],
            should=["character_voice_profiles", "kb_suggested"],
        )
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        cat = report.categories[0]
        assert cat.missing_should == ["character_voice_profiles", "kb_suggested"]
        # Should penalty is small (0.3 weight), score should still be high.
        assert cat.score > 0.5


# ── compute_adoption_report — infrastructure ───────────────────────


class TestInfrastructure:
    def test_prompt_composer_detected_via_bundled_prompts(self) -> None:
        registry = _minimal_registry()
        prompts = [_make_prompt("writing", "en", "new_chapter")]
        report = compute_adoption_report(registry, prompts)
        detail = next(
            (d for d in report.categories[0].details if d.name == "prompt_composer"),
            None,
        )
        assert detail is not None
        assert detail.adopted == 1.0

    def test_mem0_preferences_via_variables(self) -> None:
        registry = _minimal_registry(
            infra={"mem0_preferences": "required"},
        )
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        detail = next(
            (d for d in report.categories[0].details if d.name == "mem0_preferences"),
            None,
        )
        assert detail is not None
        assert detail.adopted == 1.0


# ── compute_adoption_report — inline fallbacks ─────────────────────


class TestInlineFallbacks:
    def test_fallback_penalty_reduces_score(self) -> None:
        registry = _minimal_registry()
        registry["inline_fallbacks"] = [
            {
                "file": "apps/api/narrare/writing/service.py",
                "variable": "FALLBACK_PROMPT",
                "status": "registered",
            }
        ]
        prompts = [_make_prompt("writing", "en", "new_chapter")]
        report = compute_adoption_report(registry, prompts)
        assert report.total_inline_fallbacks == 1
        # Writing should have 1 fallback
        writing = report.categories[0]
        assert writing.inline_fallbacks >= 1

    def test_no_fallbacks_no_penalty(self) -> None:
        registry = _minimal_registry()
        prompts = [_make_prompt("writing", "en", "new_chapter")]
        report = compute_adoption_report(registry, prompts)
        assert report.total_inline_fallbacks == 0


# ── compute_adoption_report — empty category ───────────────────────


class TestEmptyCategory:
    def test_no_prompts_gives_score(self) -> None:
        registry = _minimal_registry()
        report = compute_adoption_report(registry, [])
        # Even without prompts, the report should be valid.
        assert len(report.categories) == 1
        assert 0.0 <= report.categories[0].score <= 1.0


# ── compute_adoption_report — i18n coverage ────────────────────────


class TestI18n:
    def test_full_locale_coverage(self) -> None:
        registry = _minimal_registry()
        prompts = [
            _make_prompt("writing", "en", "new_chapter"),
            _make_prompt("writing", "de", "new_chapter"),
            _make_prompt("writing", "fr", "new_chapter"),
        ]
        report = compute_adoption_report(registry, prompts)
        assert report.categories[0].missing_locales == {}

    def test_partial_locale_coverage(self) -> None:
        registry = _minimal_registry()
        prompts = [
            _make_prompt("writing", "en", "new_chapter"),
        ]
        report = compute_adoption_report(registry, prompts)
        # Should report missing locales
        assert len(report.categories[0].missing_locales) > 0
