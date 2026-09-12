"""LLMIntent.SUMMARIZE route parity (R2 Slice 6 manifest reconciliation).

Layer-1 test for the SUMMARIZE prompt surface. The summarize +
band_summary templates' rogue level-2 headers were demoted (activation
slice), making the previously parse-truncated Knowledge-Base region live.
The route table previously declared NO ``optional_variables`` while the
prompt-surface manifest already listed the full activated variable set —
this file pins route↔manifest↔template parity (RULE-22 runtime↔governance
coherence), mirroring the VOICE ``template ⊆ optional`` pin convention
(see ``test_voice_drift_route.py``).

RULE-11 lesson (from character_voice + voice_check Layer 1): the route MUST
declare the same ``optional_variables`` the templates reference, or
``prepare_variables_for_template`` raises ``PromptVariableError`` for
projects lacking them. SUMMARIZE covers two governed context_modes
(``summarize`` — per-chapter, and ``band_summary`` — novel-level
aggregation), both resolving the shared intent-level optional set.

See:
    - ``scripts/architecture/prompt-surface-manifest.yaml`` SUMMARIZE entry
    - ``docs/_shared/CONSTRAINTS.md`` RULE-02b / RULE-11 / RULE-22
"""

from __future__ import annotations

from narrare_core.llm import LLMIntent
from narrare_core.prompts.route_table import (
    INTENT_TO_MODE,
    ROUTE_CONFIGS,
)
from tests.unit.core._bundled import bundled_prompts_root

_BUNDLED_ROOT = bundled_prompts_root()
_SUMMARIZE_TEMPLATE = _BUNDLED_ROOT / "analysis" / "en" / "summarize" / "system.md"
_BAND_SUMMARY_TEMPLATE = _BUNDLED_ROOT / "analysis" / "en" / "band_summary" / "system.md"

# Variables the summarize template references (post-activation surface —
# the header-demotion slice made the Knowledge-Base region parseable, so
# the previously hidden kb_* + culture_guidelines placeholders count).
# RULE-11: every one of these MUST be declared optional on the SUMMARIZE
# route config so a project lacking them renders empty rather than
# crashing the variable engine.
_SUMMARIZE_TEMPLATE_VARS = frozenset(
    {
        "project_title",
        "genre",
        "writing_language",
        "culture_guidelines",
        "chapter_title",
        "kb_characters",
        "kb_locations",
        "kb_factions",
        "kb_relationships",
        "user_preferences",
        "avoidance_patterns",
    }
)

# Variables the band_summary template references. No ``chapter_title`` —
# band summaries aggregate whole novels, not single chapters.
_BAND_SUMMARY_TEMPLATE_VARS = frozenset(
    {
        "project_title",
        "genre",
        "writing_language",
        "culture_guidelines",
        "kb_characters",
        "kb_locations",
        "kb_factions",
        "kb_relationships",
        "user_preferences",
        "avoidance_patterns",
    }
)


class TestSummarizeRouteParity:
    """SUMMARIZE route ↔ manifest ↔ template parity (R2 Slice 6)."""

    def test_route_optional_variables_mirror_manifest(self) -> None:
        """The route's optional set must equal the manifest's SUMMARIZE
        intent-level declaration (RULE-22 runtime↔governance coherence).
        """
        config = ROUTE_CONFIGS[LLMIntent.SUMMARIZE]
        assert config.optional_variables == _SUMMARIZE_TEMPLATE_VARS

    def test_summarize_template_vars_declared_optional(self) -> None:
        """RULE-11: every summarize template variable must be declared
        optional on the route.
        """
        assert _SUMMARIZE_TEMPLATE.exists()
        config = ROUTE_CONFIGS[LLMIntent.SUMMARIZE]
        missing = _SUMMARIZE_TEMPLATE_VARS - config.optional_variables
        assert not missing, (
            f"summarize template references variables not declared optional on the "
            f"SUMMARIZE route config (RULE-11 crash risk): {sorted(missing)}"
        )

    def test_band_summary_template_vars_declared_optional(self) -> None:
        """RULE-11: every band_summary template variable must be declared
        optional on the route (band_summary resolves the shared
        SUMMARIZE intent-level optional set).
        """
        assert _BAND_SUMMARY_TEMPLATE.exists()
        config = ROUTE_CONFIGS[LLMIntent.SUMMARIZE]
        missing = _BAND_SUMMARY_TEMPLATE_VARS - config.optional_variables
        assert not missing, (
            f"band_summary template references variables not declared optional on the "
            f"SUMMARIZE route config (RULE-11 crash risk): {sorted(missing)}"
        )

    def test_summarize_is_default_and_two_mode(self) -> None:
        """The SUMMARIZE default mode stays ``summarize``; ``band_summary``
        remains the second governed context_mode.
        """
        assert INTENT_TO_MODE[LLMIntent.SUMMARIZE] == "summarize"
        config = ROUTE_CONFIGS[LLMIntent.SUMMARIZE]
        assert config.allowed_context_modes == frozenset({"summarize", "band_summary"})
