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
    LLMIntent.CHAT: "chat",
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
    LLMIntent.CHAT: "",
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
        optional_variables=_COMMON_OPTIONAL_VARIABLES,
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
        required_variables=frozenset({"text_before"}),
        optional_variables=_COMMON_OPTIONAL_VARIABLES
        | frozenset({"chapter_context", "text_after"}),
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
    LLMIntent.KB_CONSISTENCY: PromptRouteConfig("kb", "consistency"),
    LLMIntent.ANALYSE: PromptRouteConfig("analysis", "review"),
    LLMIntent.CONSISTENCY: PromptRouteConfig(
        "analysis",
        "consistency",
        optional_variables=frozenset({"user_preferences", "avoidance_patterns", "extracted_facts"}),
    ),
    LLMIntent.BETA_READ: PromptRouteConfig("analysis", "beta_reader"),
    LLMIntent.PLAN: PromptRouteConfig(
        "planning",
        "outline",
        allowed_context_modes=frozenset({"outline", "temporal_consistency"}),
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
    LLMIntent.CHAT: PromptRouteConfig("chat", ""),
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
