"""Tests for mode-level scoring — evidence loading and probe integration.

Test categories:
    - TestEvidenceLoading: load_probe_evidence() edge cases
    - TestRuntimeCheckWithProbeEvidence: _check_runtime_requirements with probe overrides
    - TestComputeModeScoreWithEvidence: compute_mode_score with probe_evidence
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from adoption.scorer_modes import (  # noqa: E402
    _check_runtime_requirements,
    compute_mode_score,
    load_probe_evidence,
)

# ── TestEvidenceLoading ────────────────────────────────────────────


class TestEvidenceLoading:
    """Verify load_probe_evidence handles edge cases."""

    def test_load_probe_evidence_missing_file(self) -> None:
        """Nonexistent evidence dir returns empty dict."""
        result = load_probe_evidence("/tmp/nonexistent_evidence_dir_xyz")
        assert result == {}

    def test_load_probe_evidence_parses_jsonl(self) -> None:
        """Valid JSONL with 3 records is parsed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ev_file = Path(tmpdir) / "invocations.jsonl"
            records = [
                {"feature_id": "chat", "mode": "chat"},
                {"feature_id": "planning", "mode": "outline"},
                {"feature_id": "generation", "mode": "names"},
            ]
            with ev_file.open("w") as f:
                for rec in records:
                    f.write(json.dumps(rec) + "\n")

            result = load_probe_evidence(tmpdir)
            assert result == {
                "chat": {"chat"},
                "planning": {"outline"},
                "generation": {"names"},
            }

    def test_load_probe_evidence_skips_garbage(self) -> None:
        """Lines that are not valid JSON are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ev_file = Path(tmpdir) / "invocations.jsonl"
            with ev_file.open("w") as f:
                f.write('{"feature_id": "chat", "mode": "chat"}\n')
                f.write("not valid json\n")
                f.write('{"feature_id": "planning", "mode": "outline"}\n')
                f.write("also not json\n")
                f.write("\n")  # empty line

            result = load_probe_evidence(tmpdir)
            assert result == {
                "chat": {"chat"},
                "planning": {"outline"},
            }

    def test_load_probe_evidence_empty_file(self) -> None:
        """Empty invocations.jsonl returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ev_file = Path(tmpdir) / "invocations.jsonl"
            ev_file.touch()
            result = load_probe_evidence(tmpdir)
            assert result == {}


# ── TestRuntimeCheckWithProbeEvidence ──────────────────────────────


class TestRuntimeCheckWithProbeEvidence:
    """Verify _check_runtime_requirements with probe evidence overrides."""

    def test_evidence_flips_evidence_sink(self) -> None:
        """Probe evidence flips evidence_sink from missing to verified."""
        runtime_reqs = {
            "preference_enrichment": "required",
            "evidence_sink": "required",
            "final_validation": "required",
        }
        probe_evidence = {"chat": {"chat"}}
        details, verified = _check_runtime_requirements(
            runtime_reqs,
            probe_evidence=probe_evidence,
            mode_feature_id="chat",
            mode_name="chat",
        )
        es = next(d for d in details if d.requirement == "evidence_sink")
        assert es.evidence_status == "verified"
        assert es.note == "verified by probe evidence"
        # But overall is still False because preference_enrichment and
        # final_validation are still "required" = "missing"
        assert verified is False

    def test_evidence_does_not_flip_preference(self) -> None:
        """preference_enrichment stays missing even with probe evidence."""
        runtime_reqs = {
            "preference_enrichment": "required",
            "evidence_sink": "required",
        }
        probe_evidence = {"chat": {"chat"}}
        details, _ = _check_runtime_requirements(
            runtime_reqs,
            probe_evidence=probe_evidence,
            mode_feature_id="chat",
            mode_name="chat",
        )
        pe = next(d for d in details if d.requirement == "preference_enrichment")
        assert pe.evidence_status == "missing"

    def test_evidence_flips_final_validation_optional(self) -> None:
        """final_validation declared optional flips to verified with probes."""
        runtime_reqs = {
            "evidence_sink": "required",
            "final_validation": "optional",
        }
        probe_evidence = {"chat": {"chat"}}
        details, verified = _check_runtime_requirements(
            runtime_reqs,
            probe_evidence=probe_evidence,
            mode_feature_id="chat",
            mode_name="chat",
        )
        fv = next(d for d in details if d.requirement == "final_validation")
        # "optional" is already "verified" in default mapping, but if
        # the default ever changes, probe evidence still covers it.
        assert fv.evidence_status == "verified"
        # With evidence_sink flipped and final_validation already verified,
        # overall should be True now
        assert verified is True

    def test_evidence_noop_without_matching_mode(self) -> None:
        """Probe evidence for a different mode has no effect."""
        runtime_reqs = {"evidence_sink": "required"}
        probe_evidence = {"chat": {"chat"}}
        details, verified = _check_runtime_requirements(
            runtime_reqs,
            probe_evidence=probe_evidence,
            mode_feature_id="chat",
            mode_name="inline_suggest",
        )
        es = next(d for d in details if d.requirement == "evidence_sink")
        assert es.evidence_status == "missing"
        assert verified is False

    def test_evidence_noop_without_probe_evidence(self) -> None:
        """No probe_evidence passed means no overrides."""
        runtime_reqs = {"evidence_sink": "required"}
        details, verified = _check_runtime_requirements(runtime_reqs)
        es = next(d for d in details if d.requirement == "evidence_sink")
        assert es.evidence_status == "missing"
        assert verified is False


# ── TestComputeModeScoreWithEvidence ───────────────────────────────


class TestComputeModeScoreWithEvidence:
    """Verify compute_mode_score integrates probe evidence."""

    def test_mode_runtime_verified_with_probe_evidence(self) -> None:
        """compute_mode_score with probe evidence resolves evidence_sink."""
        ms = compute_mode_score(
            mode_name="chat",
            must_vars=["v1"],
            should_vars=[],
            infra={"prompt_composer": "required"},
            runtime_reqs={
                "preference_enrichment": "required",
                "evidence_sink": "required",
                "final_validation": "required",
            },
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
            requires_runtime_evidence=True,
            probe_evidence={"chat": {"chat"}},
            mode_feature_id="chat",
        )
        es = next(d for d in ms.runtime_details if d.requirement == "evidence_sink")
        assert es.evidence_status == "verified"
        assert es.note == "verified by probe evidence"
        # Still not fully verified (preference_enrichment and
        # final_validation remain missing)
        assert ms.runtime_verified is False

    def test_mode_runtime_verified_all_pass_with_evidence(self) -> None:
        """Probe evidence fills evidence_sink gap — all pass."""
        ms = compute_mode_score(
            mode_name="chat",
            must_vars=["v1"],
            should_vars=[],
            infra={"prompt_composer": "required"},
            runtime_reqs={
                "evidence_sink": "required",
                "kb_suggested": "provided",
            },
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
            requires_runtime_evidence=True,
            probe_evidence={"chat": {"chat"}},
            mode_feature_id="chat",
        )
        assert ms.runtime_verified is True

    def test_probe_evidence_noop_without_feature_id(self) -> None:
        """No mode_feature_id means probe evidence is not applied."""
        ms = compute_mode_score(
            mode_name="chat",
            must_vars=["v1"],
            should_vars=[],
            infra={},
            runtime_reqs={"evidence_sink": "required"},
            all_vars={"v1"},
            i18n_frac=1.0,
            has_prompts=True,
            fb_count=0,
            probe_evidence={"chat": {"chat"}},
            mode_feature_id=None,
        )
        es = next(d for d in ms.runtime_details if d.requirement == "evidence_sink")
        assert es.evidence_status == "missing"
        assert ms.runtime_verified is False
