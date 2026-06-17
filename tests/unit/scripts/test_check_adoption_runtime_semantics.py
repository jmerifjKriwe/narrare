"""ADR-045 runtime adoption status and evidence validity regressions."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import check_adoption  # noqa: E402
from adoption.scorer import AdoptionReport, compute_adoption_report  # noqa: E402
from prompt_checks import PromptFile  # noqa: E402


def _make_prompt(
    category: str = "writing",
    locale: str = "en",
    mode: str = "new_chapter",
    variables: set[str] | None = None,
) -> PromptFile:
    """Create a minimal PromptFile for runtime-adoption tests."""
    return PromptFile(
        path=Path(f"_bundled/{category}/{locale}/{mode}/system.md"),
        rel_path=f"{category}/{locale}/{mode}/system.md",
        variables=variables or {"user_preferences"},
        category=category,
        locale=locale,
        mode=mode,
    )


def _runtime_registry(
    *,
    runtime_requirements: dict[str, str] | None = None,
    requires_runtime_evidence: bool = True,
) -> dict[str, Any]:
    """Build a minimal registry with one runtime-required mode."""
    return {
        "version": "2.0.0",
        "category_defaults": {
            "writing": {
                "runtime_requirements": runtime_requirements
                or {
                    "evidence_sink": "required",
                    "final_validation": "required",
                    "preference_enrichment": "required",
                    "budget_resolution": "required",
                },
            },
        },
        "features": {
            "writing": {
                "modes": {
                    "new_chapter": {
                        "requires_runtime_evidence": requires_runtime_evidence,
                    },
                },
                "required_infrastructure": {
                    "prompt_composer": "required",
                    "meta_prompt": "required",
                    "i18n": "partial",
                },
                "context_variables": {"must": ["user_preferences"], "should": []},
            },
        },
        "inline_fallbacks": [],
        "prompt_path_compliance": {
            "writing/new_chapter": True,
        },
    }


class TestRuntimeStatusSemantics:
    """ADR-045: static scores cannot produce false adoption PASS."""

    def test_required_runtime_modes_without_evidence_are_static_only_not_pass(self) -> None:
        report = compute_adoption_report(_runtime_registry(), [_make_prompt()])

        assert report.overall_score == 1.0
        assert report.status == "STATIC_ONLY"
        assert report.status != "PASS"
        assert report.runtime_evidence_gap_count == 1

    def test_missing_runtime_records_with_evidence_source_are_governed_debt(
        self,
        tmp_path: Path,
    ) -> None:
        report = compute_adoption_report(
            _runtime_registry(),
            [_make_prompt()],
            evidence_dir=str(tmp_path),
        )

        assert report.status == "GOVERNED_DEBT"
        assert report.status != "PASS"
        assert report.categories[0].status == "GOVERNED_DEBT"

    def test_placeholder_records_do_not_satisfy_required_runtime_evidence(
        self,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "invocations.jsonl").write_text(
            json.dumps(
                {
                    "feature_id": "writing",
                    "mode": "new_chapter",
                    "audit_state": "static_verified",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (tmp_path / "final_validation.json").write_text(
            json.dumps(
                {
                    "records": [
                        {
                            "feature_id": "writing",
                            "mode": "new_chapter",
                            "audit_state": "static_verified",
                            "final_prompt_validated": False,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "preference_enrichment.json").write_text(
            json.dumps(
                {
                    "records": [
                        {
                            "feature_id": "writing",
                            "mode": "new_chapter",
                            "preference_status": "not_applicable",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "budget_resolution.json").write_text(
            json.dumps(
                {
                    "records": [
                        {
                            "feature_id": "writing",
                            "mode": "new_chapter",
                            "budget": None,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        report = compute_adoption_report(
            _runtime_registry(),
            [_make_prompt()],
            evidence_dir=str(tmp_path),
        )
        mode = report.categories[0].modes[0]

        assert mode.runtime_verified is False
        assert mode.adopted is False
        assert {d.requirement: d.evidence_status for d in mode.runtime_details} == {
            "budget_resolution": "missing",
            "evidence_sink": "missing",
            "final_validation": "missing",
            "preference_enrichment": "missing",
        }
        assert report.status != "PASS"


class TestEvidenceRepoCli:
    """ADR-045: --evidence-repo must not be a silent no-op."""

    def test_governed_debt_with_clean_baseline_keeps_ratchet_exit_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["check_adoption.py"])
        monkeypatch.setattr(check_adoption, "load_registry", lambda _path: _runtime_registry())
        monkeypatch.setattr(check_adoption, "discover_prompts", lambda _path: [_make_prompt()])
        monkeypatch.setattr(
            check_adoption,
            "compute_adoption_report",
            lambda *_args, **_kwargs: AdoptionReport(1.0, "GOVERNED_DEBT", []),
        )
        baseline_ok = type("BaselineOK", (), {"ok": True})()
        monkeypatch.setattr(
            check_adoption, "compare_section", lambda *_args, **_kwargs: baseline_ok
        )
        monkeypatch.setattr(
            check_adoption, "format_comparison", lambda *_args, **_kwargs: "baseline ok"
        )

        assert check_adoption.main() == 0

    def test_evidence_repo_flag_fails_visibly_until_adapter_exists(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["check_adoption.py", "--evidence-repo"])
        monkeypatch.setattr(check_adoption, "load_registry", lambda _path: _runtime_registry())
        monkeypatch.setattr(check_adoption, "discover_prompts", lambda _path: [_make_prompt()])
        monkeypatch.setattr(
            check_adoption,
            "compute_adoption_report",
            lambda *_args, **_kwargs: AdoptionReport(1.0, "PASS", []),
        )

        exit_code = check_adoption.main()
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "--evidence-repo" in captured.err
        assert "not supported" in captured.err
