"""PromptComposer route table data."""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.route_types import PromptRouteConfig

INTENT_TO_CATEGORY: dict[LLMIntent, str] = {
    LLMIntent.WRITE: "writing",
    LLMIntent.EXTEND: "writing",
    LLMIntent.REWRITE: "writing",
    LLMIntent.CO_AUTHOR: "writing",
    LLMIntent.KB_CREATE: "kb",
    LLMIntent.KB_IMPROVE: "kb",
    LLMIntent.KB_EXTRACT: "kb",
    LLMIntent.KB_INTERVIEW: "kb",
    LLMIntent.KB_SUGGEST: "kb",
    LLMIntent.KB_ENHANCE: "kb",
    LLMIntent.KB_WORLDBUILD: "kb",
    LLMIntent.KB_CONSISTENCY: "kb",
    LLMIntent.ANALYSE: "analysis",
    LLMIntent.CONSISTENCY: "analysis",
    LLMIntent.BETA_READ: "analysis",
    LLMIntent.PLAN: "planning",
    LLMIntent.SUMMARIZE: "analysis",
    LLMIntent.NAME_GENERATE: "generation",
    LLMIntent.EXTRACT: "analysis",
    LLMIntent.FACT_EXTRACT: "analysis",
    # ADR-055 D4: VOICE promoted from non-routeable to a multi-mode analysis
    # intent. First mode is character_voice (ANAL-008); voice_check (WRITE-010,
    # ADR-057 D3) is the second governed mode; voice_drift (ANAL-009 Phase 1,
    # ADR-073 D3) is the third. author_voice (ANAL-007) remains deferred
    # (Phase 2). Mirrors how PLAN serves several planning context_modes.
    LLMIntent.VOICE: "analysis",
    LLMIntent.SUGGEST: "writing",
    # ADR-024 / ADR-049: CHAT is a writing-craft assistant (category "writing",
    # mode "chat"). The earlier `category="chat", mode=""` drift was an
    # unauthorised deviation from ADR-024 §Decision 3 — see ADR-049 FIND-010.
    LLMIntent.CHAT: "writing",
    # ADR-069 Decision 5: DIALOGUE_COACH is the first ai_assist intent
    # (Phase 4 Task 7 — formal follow-through on the Phase 1 Task 5 stub).
    LLMIntent.DIALOGUE_COACH: "ai_assist",
}

INTENT_TO_MODE: dict[LLMIntent, str] = {
    LLMIntent.WRITE: "new_chapter",
    LLMIntent.EXTEND: "extend_chapter",
    LLMIntent.REWRITE: "rewrite_selection",
    LLMIntent.CO_AUTHOR: "co_author",
    LLMIntent.KB_IMPROVE: "improve",
    LLMIntent.KB_EXTRACT: "extract",
    LLMIntent.KB_INTERVIEW: "interview",
    LLMIntent.KB_SUGGEST: "suggest",
    LLMIntent.KB_ENHANCE: "enhance",
    LLMIntent.KB_WORLDBUILD: "worldbuilding/phase1",
    LLMIntent.KB_CONSISTENCY: "consistency",
    LLMIntent.ANALYSE: "review",
    LLMIntent.CONSISTENCY: "consistency",
    LLMIntent.BETA_READ: "beta_reader",
    LLMIntent.PLAN: "outline",
    LLMIntent.SUMMARIZE: "summarize",
    LLMIntent.NAME_GENERATE: "names",
    LLMIntent.FACT_EXTRACT: "fact_extraction",
    LLMIntent.SUGGEST: "inline_suggest",
    # ADR-055 D4: default mode for the VOICE intent. character_voice (ANAL-008)
    # is the first governed mode; voice_check (WRITE-010, ADR-057 D3) is an
    # opt-in non-default checker mode; voice_drift (ANAL-009 Phase 1, ADR-073
    # D3) is an opt-in non-default longitudinal trend-classifier mode.
    # author_voice (ANAL-007) follows later (Phase 2).
    LLMIntent.VOICE: "character_voice",
    # ADR-024 / ADR-049: CHAT mode is "chat" (not root-mode ""). Root-mode is
    # forbidden for routeable intents per ADR-049 D3.
    LLMIntent.CHAT: "chat",
    LLMIntent.DIALOGUE_COACH: "dialogue_coach",
}

_COMMON_OPTIONAL_VARIABLES = frozenset(
    {
        "avoidance_patterns",
        "character_voice_profiles",
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
        "kb_relationships",
        "kb_suggested",
        "novel_synopsis",
        "recent_chapters",
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
    # ADR-021: "readability" added for AI-powered sentence-level readability
    # analysis (ReadabilityAgent); deterministic metrics live separately in
    # analysis/readability.py.
    LLMIntent.ANALYSE: PromptRouteConfig(
        "analysis",
        "review",
        allowed_context_modes=frozenset({"review", "coreference", "pov", "readability"}),
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
    LLMIntent.SUMMARIZE: PromptRouteConfig("analysis", "summarize"),
    # ADR-055 D4: VOICE is a multi-mode analysis intent. character_voice
    # (ANAL-008) is the first governed context_mode (a *profiler*); voice_check
    # (WRITE-010, ADR-057 D3) is the second (a flag+score *checker* — distinct
    # intent, own governed template); voice_drift (ANAL-009 Phase 1, ADR-073 D3)
    # is the third (a longitudinal *trend classifier* — distinct intent, own
    # governed template). author_voice (ANAL-007) remains deferred (Phase 2 of
    # the ANAL-009 lane; own future ADR). Mirrors ANALYSE
    # (review/coreference/pov/readability) and PLAN
    # (outline/timeline/character_arc/timeline_extraction): no
    # required_variables at intent level — the resolving service (Layer 2/3)
    # supplies the chapter dialogue + deterministic voice metrics as runtime
    # input (category-3 user-channel data), exactly as coreference/readability
    # receive the analysed passage as runtime input.
    #
    # optional_variables mirrors the prompt-surface-manifest declaration for
    # analysis/character_voice + analysis/voice_check + analysis/voice_drift
    # (RULE-22 runtime↔governance coherence). The template references the KB
    # world-context variables (kb_characters / kb_locations / kb_factions /
    # kb_relationships) as optional context that aids attribution
    # normalisation; a project may legitimately have none of them, so they MUST
    # render as empty rather than crash the variable engine (RULE-11 graceful
    # degradation — prepare_variables_for_template raises PromptVariableError on
    # any template placeholder that is neither supplied nor declared optional).
    # Genre / writing_language / project_title / user_preferences /
    # avoidance_patterns are PromptContext dataclass fields (always present),
    # declared here for explicit manifest parity exactly as FACT_EXTRACT
    # declares its full optional set.
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
        allowed_context_modes=frozenset({"character_voice", "voice_check", "voice_drift"}),
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
    LLMIntent.CHAT: PromptRouteConfig("writing", "chat"),
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
