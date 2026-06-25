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
    LLMIntent.SUGGEST: "writing",
    # ADR-024 / ADR-049: CHAT is a writing-craft assistant (category "writing",
    # mode "chat"). The earlier `category="chat", mode=""` drift was an
    # unauthorised deviation from ADR-024 §Decision 3 — see ADR-049 FIND-010.
    LLMIntent.CHAT: "writing",
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
    # ADR-024 / ADR-049: CHAT mode is "chat" (not root-mode ""). Root-mode is
    # forbidden for routeable intents per ADR-049 D3.
    LLMIntent.CHAT: "chat",
}

_COMMON_OPTIONAL_VARIABLES = frozenset(
    {
        "avoidance_patterns",
        "character_voice_profiles",
        "culture_guidelines",
        "kb_factions",
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
        optional_variables=_COMMON_OPTIONAL_VARIABLES,
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
    LLMIntent.ANALYSE: PromptRouteConfig("analysis", "review"),
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
    LLMIntent.VOICE: "Voice analysis has no dedicated bundled PromptComposer template yet.",
    LLMIntent.GENERATE: "Generic generation must use a specific routed intent or feature mode.",
    LLMIntent.TITLE_GENERATE: "No title-generation feature prompt is bundled yet.",
    LLMIntent.RESEARCH: "Research synthesis has no bundled PromptComposer route yet.",
}
