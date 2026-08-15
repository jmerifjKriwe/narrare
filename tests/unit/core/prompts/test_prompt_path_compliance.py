"""Prompt-Path-Compliance Test Convention (ADR-046 D.1).

This is a **convention / documentation test**, not a behaviour test. It enforces
the rule that every audited prompt-resolving service has a corresponding
``*_prompt_path_compliance.py`` (or equivalent) test file.

What a Prompt-Path-Compliance test verifies (per ADR-046 D.1):
    1. **Service-level path assertion** — the service resolves prompts via
       ``PromptComposer.build()``, never ``PromptRegistry.resolve()`` directly.
    2. **Channel assertion** — the system prompt is passed as agent
       system/instructions, NOT concatenated into the user prompt.
    3. **No-fallback assertion** — production paths fail-fast when PromptComposer
       is unavailable; no inline fallback prompt strings.

Convention for NEW services:
    When you add a production service that resolves prompts (calls
    ``PromptComposer.build()``), you MUST:
      (a) add a ``test_*_prompt_path_compliance.py`` file covering the three
          assertions above, AND
      (b) register it in :data:`PROMPT_PATH_COMPLIANCE_REGISTRY` below.

    This test FAILS if a registered service's compliance test file is missing
    or removed, so the convention cannot silently regress.

See:
    - ``docs/architecture/decisions/ADR-046-prompt-path-compliance.md`` § D.1
    - ``docs/features/remediation/cr-02-prompt-path-retrofit.md`` § D.1
    - ``docs/_shared/CONSTRAINTS.md`` RULE-02b
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Repository root: tests/unit/core/prompts/ -> ../../../../
_REPO_ROOT = Path(__file__).resolve().parents[4]


# ---------------------------------------------------------------------------
# Registry of audited prompt-resolving services
# ---------------------------------------------------------------------------
#
# Each entry maps a service (the module that resolves prompts) to the test file
# that asserts its prompt-path compliance. Add new prompt-resolving services here
# together with their compliance test file.
#
# The four services below were the CR-02 retrofit targets (CR-AUFG-02-04..07).
# Their compliance tests guard the exact drift paths the D.2 checkers also
# detect — defence in depth (tests + checkers).

PROMPT_PATH_COMPLIANCE_REGISTRY: dict[str, str] = {
    # CR-AUFG-02-04: chat system prompt must not be concatenated into user channel.
    "apps.api.narrare.chat.chat_service.ChatService": (
        "tests/unit/api/chat/test_chat_prompt_path_compliance.py"
    ),
    # CR-AUFG-02-05: worldbuilding phase2 must use PromptComposer, not registry.
    "apps.api.narrare.kb.worldbuilding_analyzer.WorldbuildingAnalyzer": (
        "tests/unit/api/kb/test_worldbuilding_prompt_path_compliance.py"
    ),
    # CR-AUFG-02-06: temporal consistency must use PromptComposer, no app loader.
    "apps.api.narrare.planning.timeline_consistency_service.TimelineConsistencyService": (
        "tests/unit/api/planning/test_timeline_prompt_path_compliance.py"
    ),
    # CR-AUFG-02-07: writing graph must fail-fast on missing composer (no inline fallback).
    "packages.core.narrare_core.agents.writing_graph_prompts": (
        "tests/unit/core/agents/test_writing_graph_prompts.py"
    ),
    # SERIES-002: band summary must resolve via compose_invocation Mode 1
    # (SUMMARIZE + context_mode "band_summary"), no direct-build fallback.
    "apps.api.narrare.series.band_summary_service.BandSummaryService": (
        "tests/unit/api/series/test_band_summary_prompt_path_compliance.py"
    ),
    # SERIES-004: series consistency must resolve via compose_invocation
    # Mode 1 (ANALYSE + context_mode "series_consistency").
    "apps.api.narrare.series.series_consistency_service.SeriesConsistencyService": (
        "tests/unit/api/series/test_series_consistency_prompt_path_compliance.py"
    ),
}


# ---------------------------------------------------------------------------
# Convention enforcement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "service, test_file",
    sorted(PROMPT_PATH_COMPLIANCE_REGISTRY.items()),
    ids=lambda val: val.split(".")[-1] if "." in val else val,
)
@pytest.mark.mutation_inert
def test_prompt_path_compliance_test_exists(service: str, test_file: str) -> None:
    """Each registered prompt-resolving service has a compliance test file.

    ADR-046 D.1: every prompt-resolving service must have at least one
    Prompt-Path-Compliance test. This guard prevents the convention from
    silently regressing (e.g. a compliance test being deleted).
    """
    test_path = _REPO_ROOT / test_file
    assert test_path.is_file(), (
        f"Prompt-Path-Compliance test missing for {service}:\n"
        f"  expected: {test_file}\n"
        f"  found:    {test_path}\n"
        f"Per ADR-046 D.1, prompt-resolving services require a compliance test. "
        f"Create the file or remove the service from "
        f"PROMPT_PATH_COMPLIANCE_REGISTRY if it no longer resolves prompts."
    )


def test_registry_is_non_empty() -> None:
    """The compliance registry must list at least the audited services."""
    assert len(PROMPT_PATH_COMPLIANCE_REGISTRY) >= 4


def test_registry_entries_are_unique() -> None:
    """No two services may share the same compliance test file."""
    test_files = list(PROMPT_PATH_COMPLIANCE_REGISTRY.values())
    assert len(test_files) == len(set(test_files)), (
        "Duplicate compliance test files in PROMPT_PATH_COMPLIANCE_REGISTRY"
    )
