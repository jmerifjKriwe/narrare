"""Identity regression test for the ADR-074 voice-generic type extraction.

The voice-generic types ``VoiceMetrics`` and ``VoiceAnalysis`` were moved
from ``narrare_core.kb.schemas.character`` to their canonical home
``narrare_core.schemas.voice`` (ADR-074 Retrofit-Plan step 1) and are
re-exported from the old location for backward compatibility.

This test asserts the re-exports resolve to the SAME class objects (not
duplicates). It is the cheap, fast guard against an accidental
re-introduction of duplicate definitions during a future refactor: the
existing ANAL-008 / WRITE-010 / ANAL-009-Phase-1 suites already cover
*behaviour*; this test covers *identity* (SSOT — RULE-22).
"""

from __future__ import annotations

from narrare_core.kb.schemas import (
    VoiceAnalysis as VoiceAnalysis_via_package,
)
from narrare_core.kb.schemas import (
    VoiceMetrics as VoiceMetrics_via_package,
)
from narrare_core.kb.schemas.character import (
    VoiceAnalysis as VoiceAnalysis_via_character,
)
from narrare_core.kb.schemas.character import (
    VoiceMetrics as VoiceMetrics_via_character,
)
from narrare_core.schemas.voice import (
    VoiceAnalysis as VoiceAnalysis_canonical,
)
from narrare_core.schemas.voice import (
    VoiceMetrics as VoiceMetrics_canonical,
)


def test_voice_metrics_reexport_from_character_is_identical() -> None:
    """``kb.schemas.character.VoiceMetrics`` is the canonical class, not a copy."""
    assert VoiceMetrics_via_character is VoiceMetrics_canonical


def test_voice_analysis_reexport_from_character_is_identical() -> None:
    """``kb.schemas.character.VoiceAnalysis`` is the canonical class, not a copy."""
    assert VoiceAnalysis_via_character is VoiceAnalysis_canonical


def test_voice_metrics_reexport_from_package_init_is_identical() -> None:
    """``kb.schemas.VoiceMetrics`` (package path) resolves to the canonical class.

    Covers the second public import path used by
    ``tests/unit/core/kb/schemas/test_character_schema.py``.
    """
    assert VoiceMetrics_via_package is VoiceMetrics_canonical


def test_voice_analysis_reexport_from_package_init_is_identical() -> None:
    """``kb.schemas.VoiceAnalysis`` (package path) resolves to the canonical class."""
    assert VoiceAnalysis_via_package is VoiceAnalysis_canonical


def test_canonical_module_path_is_voice() -> None:
    """The canonical ``__module__`` is ``narrare_core.schemas.voice`` (SSOT home).

    Guards against a future refactor that re-imports the classes into
    ``character.py`` under new names (which would break ``isinstance`` and
    ``model_validate`` round-trips across the two paths).
    """
    assert VoiceMetrics_canonical.__module__ == "narrare_core.schemas.voice"
    assert VoiceAnalysis_canonical.__module__ == "narrare_core.schemas.voice"
