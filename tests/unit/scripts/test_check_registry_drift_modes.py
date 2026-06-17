"""Tests for scripts/check_registry_drift.py — drift *detection* behaviour.

Covers mode-prompt alignment, missing prompts, and unregistered prompt files.
The reporting surface (DriftReport, severity sort, exit-code semantics) lives
in ``test_check_registry_drift_report.py`` (split for RULE-04 file-size limit).

Validates drift detection per ADR-041 Decision 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Project root for `scripts.*` imports.
_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Same-directory imports for shared fixtures.
_DIR = str(Path(__file__).resolve().parent)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from scripts.check_registry_drift import (  # noqa: E402
    check_registry_drift,
)
from test_check_registry_drift import (  # noqa: E402
    _make_prompt_file,
    _make_registry,
    _write_env,
)

# ── TestModePromptAlignment ────────────────────────────────────────────


class TestModePromptAlignment:
    """Registered modes with matching prompt files produce no critical findings."""

    def test_aligned_modes_no_critical(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "new_chapter": {"requires_runtime_evidence": True},
                        "extend_chapter": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "new_chapter")
        _make_prompt_file(prompts_dir, "writing", "extend_chapter")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        criticals = [f for f in findings if f.severity == "critical"]
        assert criticals == []

    def test_aligned_modes_produce_info(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "draft": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "draft")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        infos = [f for f in findings if f.severity == "info"]
        assert len(infos) >= 1
        assert any("writing" in f.message for f in infos)

    def test_modeless_category_aligned(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "chat": {
                    "modes": [],
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "chat", "")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        criticals = [f for f in findings if f.severity == "critical"]
        assert criticals == []


# ── TestMissingPromptForMode ───────────────────────────────────────────


class TestMissingPromptForMode:
    """Mode in registry but no prompt file = critical finding."""

    def test_missing_prompt_critical(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "ghost_mode": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        # Don't create any prompt file for ghost_mode.

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        criticals = [f for f in findings if f.severity == "critical"]
        assert len(criticals) == 1
        assert "ghost_mode" in criticals[0].message
        assert criticals[0].category == "writing"

    def test_missing_modeless_prompt_critical(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "chat": {
                    "modes": [],
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        # No chat/en/system.md created.

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        criticals = [f for f in findings if f.severity == "critical"]
        assert len(criticals) == 1
        assert "modeless" in criticals[0].message.lower()

    def test_partial_missing_prompts(self, tmp_path: Path) -> None:
        """Two modes registered, one missing prompt -> only that one critical."""
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "present": {"requires_runtime_evidence": True},
                        "absent": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "present")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        criticals = [f for f in findings if f.severity == "critical"]
        assert len(criticals) == 1
        assert "absent" in criticals[0].message


# ── TestUnregisteredPromptFile ─────────────────────────────────────────


class TestUnregisteredPromptFile:
    """Prompt file not in registry = warning."""

    def test_unregistered_mode_warning(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "draft": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "draft")
        _make_prompt_file(prompts_dir, "writing", "unregistered_extra")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        warnings = [f for f in findings if f.severity == "warning"]
        assert len(warnings) == 1
        assert "unregistered_extra" in warnings[0].message

    def test_unregistered_category_warning(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "draft": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "draft")
        _make_prompt_file(prompts_dir, "unknown_cat", "some_mode")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        warnings = [f for f in findings if f.severity == "warning"]
        assert any("unknown_cat" in f.message for f in warnings)

    def test_skip_infrastructure_categories(self, tmp_path: Path) -> None:
        """meta/ and universal/ prompt files should not produce warnings."""
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "draft": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "draft")
        # Create infrastructure prompts -- should be ignored.
        _make_prompt_file(prompts_dir, "meta", "")
        _make_prompt_file(prompts_dir, "universal", "")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        warnings = [f for f in findings if f.severity == "warning"]
        assert not any("meta" in f.message for f in warnings)
        assert not any("universal" in f.message for f in warnings)

    def test_skip_subsystem_categories(self, tmp_path: Path) -> None:
        """Subsystem categories (e.g. wiki) with own loaders must not produce warnings.

        Regression for ADR-022 (LLM Wiki): wiki/chapter_summary and
        wiki/entity_summary are loaded by WikiPromptLoader, not by the main
        PromptComposer cascade. They must be excluded from drift detection.
        """
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "draft": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "draft")
        # Create subsystem prompts -- should be ignored (own loader per ADR-022).
        _make_prompt_file(prompts_dir, "wiki", "chapter_summary")
        _make_prompt_file(prompts_dir, "wiki", "entity_summary")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        warnings = [f for f in findings if f.severity == "warning"]
        assert not any("wiki" in f.message for f in warnings), (
            f"Wiki subsystem prompts must be skipped, got: {warnings}"
        )
