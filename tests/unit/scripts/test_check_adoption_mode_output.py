"""Mode output formatting and backward compatibility tests (ADR-039).

Tests for human/json output formatting and backward compatibility
with old registry formats.

Computation and aggregation tests are in
test_check_adoption_mode_score.py.
"""

from __future__ import annotations

import json
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
from check_adoption import (  # noqa: E402
    _format_human,
    _format_json,
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


# ── Checker output format ──────────────────────────────────────────


class TestHumanModeOutput:
    """Verify _format_human and _format_json include mode breakdown."""

    def test_human_output_shows_mode_count(self) -> None:
        """Human-readable output includes '[N modes' marker."""
        registry = _minimal_registry_v2(
            modes={"new_chapter": {}, "inline_suggest": {}},
        )
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
            _make_prompt("writing", "en", "inline_suggest", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        output = _format_human(report)
        assert "[2 modes" in output

    def test_human_output_shows_mode_scores(self) -> None:
        """Human output lists each mode with score, static, runtime, adopted."""
        registry = _minimal_registry_v2()
        prompts = [_make_prompt("writing", "en", "new_chapter", {"user_preferences"})]
        report = compute_adoption_report(registry, prompts)
        output = _format_human(report)
        assert "new_chapter" in output
        assert "static" in output
        assert "runtime" in output
        assert "adopted" in output

    def test_human_output_shows_runtime_failures(self) -> None:
        """Human output details runtime failures per mode."""
        registry = _minimal_registry_v2(
            cat_runtime={"feature_a": "required"},
        )
        prompts = [_make_prompt("writing", "en", "new_chapter", {"user_preferences"})]
        report = compute_adoption_report(registry, prompts)
        output = _format_human(report)
        assert "feature_a" in output
        assert "required" in output

    def test_json_output_includes_modes_per_category(self) -> None:
        """JSON output has a 'modes' array per category."""
        registry = _minimal_registry_v2()
        prompts = [_make_prompt("writing", "en", "new_chapter", {"user_preferences"})]
        report = compute_adoption_report(registry, prompts)
        data = json.loads(_format_json(report))
        assert len(data["categories"]) == 1
        cat = data["categories"][0]
        assert "modes" in cat
        assert len(cat["modes"]) == 1
        assert cat["modes"][0]["mode"] == "new_chapter"

    def test_json_output_includes_runtime_details(self) -> None:
        """JSON output includes runtime_details for each mode."""
        registry = _minimal_registry_v2(
            cat_runtime={"feature_a": "required"},
        )
        prompts = [_make_prompt("writing", "en", "new_chapter", {"user_preferences"})]
        report = compute_adoption_report(registry, prompts)
        data = json.loads(_format_json(report))
        mode = data["categories"][0]["modes"][0]
        assert "runtime_details" in mode
        assert len(mode["runtime_details"]) == 1
        rt = mode["runtime_details"][0]
        assert rt["requirement"] == "feature_a"
        assert rt["declared"] == "required"
        assert rt["evidence_status"] == "missing"


# ── Backward compatibility ─────────────────────────────────────────


class TestBackwardCompat:
    """Verify old YAML format still works with v2.0.0 scorer."""

    def test_list_format_modes_still_work(self) -> None:
        """Old list-of-strings mode format still produces mode scores."""
        registry = _minimal_registry_v2()
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        assert len(report.categories[0].modes) == 1
        assert report.categories[0].modes[0].mode == "new_chapter"

    def test_no_runtime_requirements_still_works(self) -> None:
        """Registry without category_defaults still produces valid report."""
        registry = _minimal_registry_v2()
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
        ]
        report = compute_adoption_report(registry, prompts)
        assert report.overall_score > 0
        mode = report.categories[0].modes[0]
        assert mode.runtime_verified is False
        assert len(mode.runtime_details) == 0

    def test_existing_category_score_unchanged(self) -> None:
        """Same effective config produces same category score."""
        registry = _minimal_registry_v2()
        prompts = [
            _make_prompt("writing", "en", "new_chapter", {"user_preferences"}),
        ]
        report_a = compute_adoption_report(registry, prompts)

        v2 = _minimal_registry_v2(modes={"new_chapter": {}}, must=["user_preferences"])
        report_b = compute_adoption_report(v2, prompts)

        assert report_b.categories[0].score == report_a.categories[0].score
        assert report_b.categories[0].status == report_a.categories[0].status
