"""PromptComposer route table data.

The intent→category/mode lookup dicts (``INTENT_TO_CATEGORY`` /
``INTENT_TO_MODE``) are defined in :mod:`route_table_intents` and re-exported
here (RULE-04 modularisation — ``route_table.py`` previously sat at the 400-line
hard limit; see ADR-079 Consequences). Importing them from this module keeps the
historical public surface unchanged.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.route_table_intents import (
    INTENT_TO_CATEGORY as INTENT_TO_CATEGORY,
)
from narrare_core.prompts.route_table_intents import (
    INTENT_TO_MODE as INTENT_TO_MODE,
)
from narrare_core.prompts.route_types import PromptRouteConfig

_COMMON_OPTIONAL_VARIABLES = frozenset(
    {
        "avoidance_patterns",
        "character_voice_profiles",
        # ADR-074 / ANAL-007: author-voice analogue of
        # {{character_voice_profiles}}. Declared optional so routes that do
        # NOT run full KB assembly (REWRITE, EXTEND, …) render it as ""
        # instead of raising PromptVariableError (RULE-11 graceful).
        "author_voice",
        "cross_session_context",
        "culture_guidelines",
        # CR-AUFG-04-06 / CR-AUFG-04-04: KB diagnostic vars surfaced into the
        # writing templates. Declared optional so routes that do NOT run full
        # KB assembly (REWRITE, EXTEND, …) render them as "" instead of raising
        # PromptVariableError at compose time (RULE-11 graceful degradation).
        # When a route supplies them via WritingContext.to_prompt_variables(),
        # the supplied value wins (prepare_variables_for_template short-circuits
        # on present vars). See test_writing_kb_var_routing.py for the guard.
        "kb_context_warnings",
        "kb_factions",
        "kb_other",
        # ADR-050 P1-D / Tier-5 KB injection (PO ruling 1B, 2026-09-10):
        # pinned-notes / magic-system / timeline tier blocks. Declared
        # optional for the same RULE-11 reason as the kb_* vars above.
        "kb_pinned",
        "kb_relationships",
        "kb_suggested",
        "kb_systems",
        "kb_timelines",
        "novel_synopsis",
        "recent_chapters",
        # Spec 2 / SERIES-002: series-history block. Declared optional so
        # routes that do not run series-history assembly (and standalone
        # novels) render it as "" instead of raising PromptVariableError
        # (RULE-11 graceful). When supplied via WritingContext, the value wins.
        "series_history",
        "style_profile",
        "timeline_position",
        "tone_instructions",
        "user_preferences",
        "world_context",
    }
)

ROUTE_CONFIGS: dict[LLMIntent, PromptRouteConfig] = {
    LLMIntent.WRITE: PromptRouteConfig(
        "writing",
        "new_chapter",
        required_variables=frozenset({"chapter_outline"}),
        optional_variables=_COMMON_OPTIONAL_VARIABLES,
        allowed_context_modes=frozenset(
            {"new_chapter", "scene_by_scene", "interview", "interactive_session"}
        ),
    ),
    LLMIntent.EXTEND: PromptRouteConfig(
        "writing",
        "extend_chapter",
        required_variables=frozenset({"existing_content"}),
        optional_variables=_COMMON_OPTIONAL_VARIABLES,
    ),
    LLMIntent.REWRITE: PromptRouteConfig(
        "writing",
        "rewrite_selection",
        required_variables=frozenset({"selection_text"}),
        optional_variables=_COMMON_OPTIONAL_VARIABLES
        | frozenset(
            {
                # Rewrite-specific injected instructions (always provided at
                # runtime by stream_rewrite; declared optional so the variable
                # engine renders them as empty when absent and the ORPHAN /
                # provenance gates recognise them as route-reachable).
                "rewrite_mode_instructions",
                # CR-AUFG-07-22: style-variant creative direction.
                "style_variant_instructions",
            }
        ),
    ),
    LLMIntent.CO_AUTHOR: PromptRouteConfig(
        "writing",
        "co_author",
        required_variables=frozenset({"selection_text"}),
        optional_variables=_COMMON_OPTIONAL_VARIABLES
        | frozenset(
            {
                # CR-AUFG-07-22: style-variant creative direction (mirrors
                # REWRITE; the co-author pipeline follows the rewrite pattern).
                "style_variant_instructions",
            }
        ),
    ),
    LLMIntent.SUGGEST: PromptRouteConfig(
        "writing",
        "inline_suggest",
        # WRITE-009: SUGGEST is now a multi-mode intent. Required variables are
        # context-mode-dependent (text_before for inline_suggest; story context
        # for story_suggest), so they are not declared at intent level. The
        # inline_suggest service validates text_before at runtime.
        optional_variables=_COMMON_OPTIONAL_VARIABLES
        | frozenset({"chapter_context", "text_after"}),
        allowed_context_modes=frozenset({"inline_suggest", "story_suggest"}),
    ),
    LLMIntent.KB_CREATE: PromptRouteConfig(
        "kb",
        None,
        optional_variables=frozenset({"world_context", "user_preferences", "avoidance_patterns"}),
        allowed_context_modes=frozenset({"interview", "suggest", "enhance"}),
    ),
    LLMIntent.KB_IMPROVE: PromptRouteConfig("kb", "improve"),
    LLMIntent.KB_EXTRACT: PromptRouteConfig(
        "kb",
        "extract",
        optional_variables=frozenset({"world_context", "user_preferences", "avoidance_patterns"}),
    ),
    LLMIntent.KB_INTERVIEW: PromptRouteConfig("kb", "interview"),
    LLMIntent.KB_SUGGEST: PromptRouteConfig("kb", "suggest"),
    LLMIntent.KB_ENHANCE: PromptRouteConfig("kb", "enhance"),
    LLMIntent.KB_WORLDBUILD: PromptRouteConfig(
        "kb",
        "worldbuilding/phase1",
        optional_variables=frozenset({"world_context", "user_preferences", "avoidance_patterns"}),
        allowed_context_modes=frozenset({"worldbuilding/phase1", "worldbuilding/phase2"}),
    ),
    LLMIntent.KB_CONSISTENCY: PromptRouteConfig(
        "kb",
        "consistency",
        # ADR-054 D5: "merge" added for KB merge analysis (KBMergeService);
        # "consistency" is the default template mode and is now also declared
        # as an explicit context-mode. MODE_REQUIRED_VARS["kb"]["merge"]
        # requires world_context / entity_type / candidate_pairs in the
        # kb/<lang>/merge/system.md template.
        allowed_context_modes=frozenset({"consistency", "merge"}),
    ),
    # ANAL-005: "coreference" added for coreference resolution analysis
    # (CoreferenceAgent). "review" remains the default general-review mode.
    # ANAL-004: "pov" added for POV detection analysis (POVDetectionAgent).
    # ADR-021: "readability" (ReadabilityAgent); deterministic metrics in analysis/readability.py.
    # SERIES-004: "series_consistency" — canon-contradiction (SeriesConsistencyAgent).
    LLMIntent.ANALYSE: PromptRouteConfig(
        "analysis",
        "review",
        allowed_context_modes=frozenset(
            {"review", "coreference", "pov", "readability", "series_consistency"}
        ),
    ),
    LLMIntent.CONSISTENCY: PromptRouteConfig(
        "analysis",
        "consistency",
        optional_variables=frozenset({"user_preferences", "avoidance_patterns", "extracted_facts"}),
    ),
    LLMIntent.BETA_READ: PromptRouteConfig(
        "analysis",
        "beta_reader",
        # ADR-049 Phase D: beta_reader_deepdive is loaded by beta_reader_service
        # as a deeper-review sub-mode. Declared here so the ORPHAN-TEMPLATE
        # gate recognises it as reachable (previously undeclared governance gap).
        allowed_context_modes=frozenset({"beta_reader", "beta_reader_deepdive"}),
    ),
    LLMIntent.PLAN: PromptRouteConfig(
        "planning",
        "outline",
        # ADR-049 D7: "timeline" added for timeline-analysis (FIND-011).
        # "temporal_consistency" remains for conflict-detection on existing
        # events (separate use-case; governed template already exists).
        # ADR-054 D4: "character_arc" (CharacterArcService) and
        # "timeline_extraction" (TemporalExtractionService) added as the final
        # two inline-feature-prompt debt migrations. Note: "timeline_extraction"
        # *extracts* temporal expressions per chapter (TemporalExtractionAgent),
        # while "timeline" *generates* a chronological timeline from summaries
        # (TimelineAgent) — different agent/task/service, no semantic overlap.
        allowed_context_modes=frozenset(
            {
                "outline",
                "temporal_consistency",
                "timeline",
                "character_arc",
                "timeline_extraction",
            }
        ),
    ),
    # SERIES-002 (Spec 2 Task 2): SUMMARIZE gains a context_modes list. The
    # default mode `summarize` is the per-chapter summary (ChapterSummaryAgent);
    # `band_summary` aggregates chapter summaries into a novel-level band
    # summary (BandSummaryAgent) — used by SeriesHistoryTier to give later
    # series volumes awareness of prior novels. Mirrors ANALYSE
    # (review/coreference/pov/readability) and PLAN (outline/timeline/...):
    # no required_variables at intent level — the chapter summaries / novel
    # metadata are category-3 runtime data supplied as the run prompt (user
    # channel), exactly as coreference/readability receive the analysed
    # passage as runtime input. analysis-category convention: no
    # MODE_REQUIRED_VARS entry (see test_non_writing_category_has_no_mode_requirements).
    #
    # R2 Slice 6 manifest reconciliation (2026-09-12): the summarize +
    # band_summary header demotion activated the previously parse-truncated
    # Knowledge-Base region, so optional_variables now mirrors the
    # prompt-surface-manifest declaration (SUMMARIZE intent-level +
    # context_modes entries — RULE-22 runtime↔governance coherence): the
    # PromptContext fields (project_title / genre / writing_language /
    # chapter_title / user_preferences / avoidance_patterns), the
    # composer-seam culture_guidelines, and the four kb_* slots supplied
    # via the ADR-067 provider spread. A project may legitimately lack any
    # of them, so each MUST render as empty rather than crash the variable
    # engine (RULE-11 graceful degradation — prepare_variables_for_template
    # raises PromptVariableError on any template placeholder that is
    # neither supplied nor declared optional).
    LLMIntent.SUMMARIZE: PromptRouteConfig(
        "analysis",
        "summarize",
        optional_variables=frozenset(
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
        ),
        allowed_context_modes=frozenset({"summarize", "band_summary"}),
    ),
    # ADR-055 D4: VOICE is a multi-mode analysis intent. character_voice
    # (ANAL-008) is the first governed context_mode (a *profiler*); voice_check
    # (WRITE-010, ADR-057 D3) is the second (a flag+score *checker* — distinct
    # intent, own governed template); voice_drift (ANAL-009 Phase 1, ADR-073 D3)
    # is the third (a longitudinal *trend classifier* — distinct intent, own
    # governed template); author_voice (ANAL-007, ADR-074) is the fourth (an
    # author-voice *profiler* for narrator prose — distinct intent, own governed
    # template); author_voice_drift (ANAL-009 Phase 2B) is the fifth (a
    # longitudinal *narrator trend classifier* — distinct intent, own governed
    # template). Mirrors ANALYSE (review/coreference/pov/readability) and PLAN
    # (outline/timeline/character_arc/timeline_extraction): no
    # required_variables at intent level — the resolving service (Layer 2/3)
    # supplies the chapter prose + precomputed metrics as runtime input
    # (category-3 user-channel data), exactly as coreference/readability
    # receive the analysed passage as runtime input.
    #
    # optional_variables mirrors the prompt-surface-manifest declaration for
    # analysis/character_voice + analysis/voice_check + analysis/voice_drift +
    # analysis/author_voice + analysis/author_voice_drift (RULE-22
    # runtime↔governance coherence). The template references the KB
    # world-context variables (kb_characters / kb_locations / kb_factions /
    # kb_relationships) as optional context that aids attribution /
    # interpretation; a project may legitimately have none of them, so they
    # MUST render as empty rather than crash the variable engine (RULE-11
    # graceful degradation — prepare_variables_for_template raises
    # PromptVariableError on any template placeholder that is neither supplied
    # nor declared optional). Genre / writing_language / project_title /
    # user_preferences / avoidance_patterns are PromptContext dataclass fields
    # (always present), declared here for explicit manifest parity exactly as
    # FACT_EXTRACT declares its full optional set.
    LLMIntent.VOICE: PromptRouteConfig(
        "analysis",
        "character_voice",
        optional_variables=frozenset(
            {
                "project_title",
                "genre",
                "writing_language",
                "kb_characters",
                "kb_locations",
                "kb_factions",
                "kb_relationships",
                "user_preferences",
                "avoidance_patterns",
            }
        ),
        allowed_context_modes=frozenset(
            {
                "character_voice",
                "voice_check",
                "voice_drift",
                "author_voice",
                "author_voice_drift",
            }
        ),
    ),
    LLMIntent.NAME_GENERATE: PromptRouteConfig("generation", "names"),
    LLMIntent.EXTRACT: PromptRouteConfig(
        "analysis",
        None,
        optional_variables=frozenset({"user_preferences", "avoidance_patterns"}),
        allowed_context_modes=frozenset({"preferences", "remap"}),
    ),
    LLMIntent.FACT_EXTRACT: PromptRouteConfig(
        "analysis",
        "fact_extraction",
        optional_variables=frozenset(
            {
                "user_preferences",
                "avoidance_patterns",
                "genre",
                "kb_entities",
                "existing_entity_names",
                "timeline_events",
            }
        ),
    ),
    # ADR-024 / ADR-049 D1: CHAT routing restored to the authorised ADR-024
    # values. The previous `PromptRouteConfig("chat", "")` was an unauthorised
    # drift that created a root-mode path (`chat/en/system.md`) invisible to
    # PromptManagement and inconsistent with the manifest template path.
    # WS interview context-mode (2026-09-11 WS supply slice): the governed
    # interview template demands {{tone_instructions}}, which has no runtime
    # owner on the WebSocket interview path (tone instructions are resolved
    # from DB settings by the tone resolver on the extend/rewrite routes
    # only). Declared optional so it renders "" instead of raising
    # PromptVariableError at compose (RULE-11 graceful, probe-proven demand).
    LLMIntent.CHAT: PromptRouteConfig(
        "writing",
        "chat",
        optional_variables=frozenset({"tone_instructions"}),
    ),
    # ADR-069 Decision 5 + Decision 10: DIALOGUE_COACH route entry. Phase 1
    # Task 5 deferred this to Phase 4 step 17 — this is that step.
    # optional_variables mirrors the prompt-surface-manifest declaration
    # (RULE-22 runtime ↔ governance coherence). The adaptive variables
    # (user_preferences / style_constraints / avoidance_patterns /
    # character_voice_profiles) are populated by AdaptiveContextEnricher
    # (Phase 2). text_to_analyze is USER_CONTENT_VARS — must be XML-tag-
    # wrapped in the governed template per RULE-22 §6. {{mode}} and
    # {{characters}} are SYSTEM_VARS (Phase 1 Task 5 registered them).
    # No required_variables — mirrors VOICE / ANALYSE (runtime content
    # supplied by the service as the run prompt).
    LLMIntent.DIALOGUE_COACH: PromptRouteConfig(
        "ai_assist",
        "dialogue_coach",
        optional_variables=frozenset(
            {
                "project_title",
                "genre",
                "writing_language",
                "user_preferences",
                "style_constraints",
                "avoidance_patterns",
                "character_voice_profiles",
                "mode",
                "characters",
                "text_to_analyze",
            }
        ),
        allowed_context_modes=frozenset({"dialogue_coach"}),
    ),
}

CONTEXT_MODE_REQUIRED_INTENTS: dict[LLMIntent, str] = {
    LLMIntent.KB_CREATE: (
        "KB creation is an aggregate assisted flow; callers must choose an "
        "existing KB mode such as interview, suggest, or enhance."
    ),
    LLMIntent.EXTRACT: (
        "General extraction has no canonical bundled template; production "
        "callers must provide a governed feature mode such as preferences."
    ),
}

NON_ROUTEABLE_INTENTS: dict[LLMIntent, str] = {
    LLMIntent.SENTIMENT: "Sentiment analysis is handled by deterministic NLP analyzers.",
    # ADR-055 D4: VOICE removed — it is now a routeable analysis intent
    # (character_voice context_mode + governed EN template).
    LLMIntent.GENERATE: "Generic generation must use a specific routed intent or feature mode.",
    LLMIntent.TITLE_GENERATE: "No title-generation feature prompt is bundled yet.",
    LLMIntent.RESEARCH: "Research synthesis has no bundled PromptComposer route yet.",
}
