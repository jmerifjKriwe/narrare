"""
LLM Intent definitions and model routing types.

Every LLM call carries an intent. Intents are grouped into categories
for user-configurable model routing. The actual model resolution is
handled by ``ModelRoutingResolver`` implementations — this module
defines the types only.

Removed (configurable-model-routing):
    - ``MODEL_ROUTING`` dict — hardcoded routing replaced by runtime resolution
    - ``get_model_config()`` — replaced by ``ModelRoutingResolver.resolve()``
    - ``ModelConfig`` — replaced by ``ResolvedModelConfig``

See: openspec/changes/configurable-model-routing/design.md (D7)
"""

from __future__ import annotations

from enum import StrEnum


class LLMIntent(StrEnum):
    """All possible LLM operation intents in Narrare.

    Each intent has a defined semantic scope. When adding a new intent:
    - Document what it DOES and what it does NOT do
    - Check for scope overlap with existing intents
    - Register in _INTENT_TO_CATEGORY and _INTENT_TO_MODE in composer.py
    """

    # ------------------------------------------------------------------
    # Writing operations — chapter-level prose generation
    # ------------------------------------------------------------------

    WRITE = "write"
    """Generate new chapter content from outline.

    Scope: Full chapter prose generation from scratch. Uses outline + KB
    context to produce a complete chapter draft in a single generation.
    Input: {{chapter_outline}}, {{kb_characters/locations/factions}}, {{recent_chapters}},
    {{novel_synopsis}}, {{style_profile}}, {{chapter_voice_profiles}}.
    Output: Chapter prose in target language.
    NOT: Continue/extend existing text (use EXTEND). NOT: Overwrite a
    selection (use REWRITE). NOT: Scene-by-scene incremental (same intent,
    different mode).
    """

    EXTEND = "extend"
    """Extend existing chapter content from a continuation point.

    Scope: Seamlessly continue existing text from a [CONTINUE FROM HERE]
    marker. Matches style, voice, and pacing of the surrounding text.
    Input: {{existing_content}}, surrounding KB context, {{extend_length}}.
    Output: Continuation prose only — no meta-commentary.
    NOT: Full chapter from outline (use WRITE). NOT: Rewrite existing
    text (use REWRITE).
    """

    REWRITE = "rewrite"
    """Rewrite a specific text selection with author direction.

    Scope: Targeted rewrite of a selected passage. Surrounding context
    (before/after) provided for style matching. Produces N alternatives.
    Input: {{selection_text}}, {{context_before/after}}, {{rewrite_mode_instructions}},
    {{count}} (number of alternatives).
    Output: N alternatives wrapped in <alternative> tags.
    NOT: Free-form continuation (use EXTEND). NOT: Full chapter generation
    (use WRITE). NOT: Minor improvement without rewrite mode (use CO_AUTHOR).
    """

    CO_AUTHOR = "co_author"
    """Collaborative writing — targeted improvement of existing text.

    Scope: Focused improvement of a passage within selected categories
    (word choice, pacing, dialogue quality, description, etc.). Preserves
    author's voice and structure.
    Input: {{selection_text}}, {{context_before/after}}, {{co_author_focus_instructions}}.
    Output: Complete revised passage (single version).
    NOT: Multiple rewrite alternatives (use REWRITE). NOT: Free-form
    continuation (use EXTEND).
    """

    # ------------------------------------------------------------------
    # Analysis operations — reading, evaluating, checking text
    # ------------------------------------------------------------------

    ANALYSE = "analyse"
    """General-purpose text analysis.

    Scope: Multi-dimension analysis covering readability, sentence
    structure, POV consistency, pacing, dialogue quality, description
    effectiveness. Used for the "review" and general analysis prompts.
    Input: Chapter text + KB context + analysis focus parameters.
    Output: Structured feedback with issues and suggestions.
    NOT: Genre-specific beta reading (use BETA_READ). NOT: Sentiment
    analysis (use SENTIMENT). NOT: Consistency checking (use CONSISTENCY).
    """

    SENTIMENT = "sentiment"
    """Sentiment and emotional tone analysis.

    Scope: Analyze emotional arc and sentiment progression across a
    chapter or section. Identifies emotional beats, mood shifts, and
    tonal patterns.
    Input: Chapter text.
    Output: Sentiment scores and emotional arc description.
    NOT: General analysis (use ANALYSE). NOT: Consistency checking
    (use CONSISTENCY).
    """

    CONSISTENCY = "consistency"
    """Cross-chapter consistency checking.

    Scope: CHAPTER-level consistency. Compares chapter prose against
    KB entity data and across chapters. Checks character, timeline,
    world, and plot consistency.
    Input: {{chapter_texts}} (multiple chapters), {{kb_entities}},
    {{check_types}} (character/timeline/world/plot).
    Output: JSON with issues (error/warning/info).
    NOT: KB entry-internal consistency (use KB_CONSISTENCY).
    NOT: Worldbuilding cross-entity consistency (use KB_WORLDBUILD phase2).
    """

    BETA_READ = "beta_read"
    """Beta reader simulation — reader-perspective feedback.

    Scope: Evaluates chapter from a reader's perspective across 5
    dimensions: plot, character, prose, pacing, reader experience.
    Genre-sensitive assessment with specific text references.
    Input: {{chapter_text}}, {{chapter_titles}}, KB context,
    {{focus_categories}}, {{genre}}.
    Output: JSON with strengths, feedback items, reader questions,
    and dimension scores (1-10).
    NOT: Line-level editing (use ANALYSE). NOT: Consistency checking
    (use CONSISTENCY).
    """

    VOICE = "voice"
    """Voice and style analysis.

    Scope: Analyze author's voice, narrative distance, stylistic
    patterns, and character dialogue distinctiveness.
    Input: Chapter text.
    Output: Voice profile with stylistic markers and patterns.
    NOT: General analysis (use ANALYSE). NOT: Beta reading (use BETA_READ).
    """

    # ------------------------------------------------------------------
    # Knowledge base operations — entity creation, improvement, extraction
    # ------------------------------------------------------------------

    KB_CREATE = "kb_create"
    """Interactive KB entity creation via structured interview.

    Scope: Guides author through creating a new KB entity by asking
    structured questions about template fields. Builds entity field
    by field through dialogue.
    Input: {{template_structure}}, {{world_context}}, author answers.
    Output: JSON with completed entity fields or draft with progress.
    NOT: Fill a single field suggestion (use KB_SUGGEST).
    NOT: Bulk entity enhancement (use KB_ENHANCE).
    """

    KB_IMPROVE = "kb_improve"
    """KB entry improvement analysis.

    Scope: Analyzes an existing KB entry and identifies specific,
    actionable improvement opportunities. Does NOT generate content —
    identifies what is missing or weak.
    Input: {{entity_type}}, {{template_structure}}, {{entry_content}},
    {{existing_relationships}}, {{world_context}}.
    Output: JSON with suggestions (add_field/connect/expand/reorganize),
    completeness_score, overall_assessment.
    NOT: Content generation (use KB_ENHANCE). NOT: Contradiction checking
    (use KB_CONSISTENCY). NOT: Single-field suggestion (use KB_SUGGEST).
    """

    KB_EXTRACT = "kb_extract"
    """Extract entities from chapter text.

    Scope: Scans chapter prose for new entities, entity updates,
    relationships, and conflicts with existing KB data.
    Input: Chapter text, {{existing_entity_names}}, {{chapter_title}}.
    Output: JSON with extraction items (new_entity/update_entity/
    relationship/conflict) with confidence scores and source quotes.
    NOT: Interactive entity creation (use KB_CREATE).
    NOT: Entity enhancement (use KB_ENHANCE).
    """

    KB_INTERVIEW = "kb_interview"
    """Ask the author a single focused question about a KB field.

    Scope: One-question-at-a-time interview mode. Picks the most
    important unanswered template field and asks the author about it.
    Input: {{template_structure}}, {{existing_answers}}, {{world_context}}.
    Output: JSON with mode="question", field_key, question text.
    NOT: Suggest a value (use KB_SUGGEST). NOT: Bulk generation (use KB_ENHANCE).
    NOT: Full entity creation flow (use KB_CREATE).
    """

    KB_SUGGEST = "kb_suggest"
    """Suggest a well-reasoned value for a specific KB template field.

    Scope: Single-field suggestion mode. Given a target field and
    existing context, proposes the best value with justification.
    Input: {{template_structure}}, {{existing_answers}}, {{world_context}},
    {{target_field}}, {{target_field_description}}.
    Output: JSON with mode="suggestion", field_key, suggested value,
    reasoning, context_used.
    NOT: Ask the author a question (use KB_INTERVIEW).
    NOT: Improve the whole entry (use KB_IMPROVE).
    """

    KB_ENHANCE = "kb_enhance"
    """Generate or expand a KB entity entry with multiple fields.

    Scope: Bulk entity generation. Fills multiple template fields at
    once based on partial existing answers and world context. Can
    produce complete entries or drafts.
    Input: {{entity_type}}, {{template_structure}}, {{existing_answers}},
    {{world_context}}.
    Output: JSON with mode (complete|draft), entry fields, reasoning,
    progress score.
    NOT: Single-field suggestion (use KB_SUGGEST).
    NOT: Interactive interview (use KB_INTERVIEW or KB_CREATE).
    """

    KB_WORLDBUILD = "kb_worldbuild"
    """Worldbuilding analysis — gap detection, connections, consistency.

    Scope: Two-phase worldbuilding analysis. Phase 1: Detect gaps
    (missing entity types, fields, connections, descriptions) and
    suggest connections. Phase 2: Cross-entity consistency checking
    for specific entity pairs.
    Input (Phase 1): {{entity_summaries}}, {{template_structures}},
    {{existing_relationships}}, {{available_rel_types}}.
    Input (Phase 2): {{candidate_pairs}}, {{entity_details}}.
    Output: JSON with gaps, connection suggestions, consistency issues.
    NOT: Single-entry consistency (use KB_CONSISTENCY).
    NOT: Cross-chapter consistency (use CONSISTENCY).
    """

    KB_CONSISTENCY = "kb_consistency"
    """KB entry-internal consistency checking.

    Scope: ENTITY-level consistency. Checks a single KB entry for
    internal field contradictions — cross-field values that logically
    conflict within the same entry.
    Input: {{entity_type}}, {{template_structure}}, {{entry_content}}.
    Output: JSON with issues (critical/major/minor), suggested resolutions.
    NOT: Cross-chapter consistency (use CONSISTENCY).
    NOT: Cross-entity worldbuilding consistency (use KB_WORLDBUILD phase2).
    """

    # ------------------------------------------------------------------
    # Planning operations — story structure, scene planning
    # ------------------------------------------------------------------

    PLAN = "plan"
    """Scene/structure planning.

    Scope: Generate chapter outlines, scene breakdowns, and story
    structure plans. Can produce multiple variant outlines.
    Input: {{project_title}}, {{genre}}, {{tone}}, {{kb_characters/locations}},
    {{variant_count}}.
    Output: Structured outline with scenes, chapter titles, narrative flow.
    NOT: Character arc planning (no dedicated intent — uses PLAN).
    NOT: Timeline analysis (no dedicated intent — uses PLAN).
    """

    SUMMARIZE = "summarize"
    """Chapter/section summarization.

    Scope: Condense chapter content into concise plot-relevant summary
    with key narrative beats. Present tense, no editorializing.
    Input: Chapter text, {{chapter_title}}, {{genre}}, KB context.
    Output: 2-4 sentence summary + 2-5 key points.
    NOT: Reader-perspective analysis (use BETA_READ).
    NOT: Consistency checking (use CONSISTENCY).
    """

    # ------------------------------------------------------------------
    # Generation operations — structured content generation
    # ------------------------------------------------------------------

    GENERATE = "generate"
    """General structured generation.

    Scope: Generate structured content (not chapter prose) based on
    parameters. Fallback intent for generation tasks without a specific
    intent.
    Input: Task-specific parameters and context.
    Output: Structured data in requested format.
    NOT: Name generation (use NAME_GENERATE).
    NOT: Title generation (use TITLE_GENERATE).
    """

    NAME_GENERATE = "name_generate"
    """Name generation for characters, places, etc.

    Scope: Generate fiction-appropriate names matching specified type,
    style, gender, and cultural context. Avoids duplicates with existing
    project names.
    Input: {{name_type}}, {{count}}, {{gender}}, {{writing_language}},
    {{explanation_language}}, {{existing_names}}.
    Output: JSON array of names with optional pronunciation and meaning.
    NOT: Title generation (use TITLE_GENERATE).
    NOT: General structured generation (use GENERATE).
    """

    TITLE_GENERATE = "title_generate"
    """Title generation for chapters, novels, etc.

    Scope: Generate compelling titles that match genre conventions
    and story context. Avoids duplicates with existing titles.
    Input: Story context, genre, existing titles.
    Output: List of suggested titles with brief rationale.
    NOT: Name generation (use NAME_GENERATE).
    NOT: General structured generation (use GENERATE).
    """

    # ------------------------------------------------------------------
    # Extraction operations — pull structured data from text
    # ------------------------------------------------------------------

    EXTRACT = "extract"
    """General structured extraction from text.

    Scope: Extract structured information from arbitrary text. Used
    for tasks like extracting character traits, plot points, or
    thematic elements.
    Input: Source text + extraction schema/parameters.
    Output: Structured data matching the schema.
    NOT: KB extraction (KB_EXTRACT), analysis (ANALYSE),
    structured fact extraction (FACT_EXTRACT).
    """

    FACT_EXTRACT = "fact_extract"
    """Structured fact extraction with provenance (ADR-044 Stage 1).

    Extract facts from prose, KB, timeline with provenance+confidence.
    Reusable for KB-007, ANAL-005. NOT: KB_EXTRACT, CONSISTENCY.
    """

    SUGGEST = "suggest"
    """Quick inline suggestions.

    Scope: Generate short, targeted suggestions — inline text completion,
    story development suggestions, KB value ideas. Fast, low-token
    operations.
    Input: Varies by mode: {{text_before/after}} for inline, story
    context for story suggestions.
    Output: Short continuation text or structured suggestion list.
    NOT: Full chapter generation (use WRITE).
    NOT: KB-specific field suggestion (use KB_SUGGEST).
    """

    # ------------------------------------------------------------------
    # Chat — conversational writing assistant
    # ------------------------------------------------------------------

    CHAT = "chat"
    """General story assistant chat.

    Scope: Conversational mode. Answers questions about the author's
    project, writing craft, worldbuilding, and story structure.
    Does NOT generate prose unless explicitly requested. Uses
    conversation history for continuity.
    Input: {{conversation_history}}, project/KB context, user message.
    Output: Conversational response in natural prose.
    NOT: Generate chapter prose (use WRITE). NOT: Structured analysis
    (use ANALYSE or BETA_READ).
    """

    RESEARCH = "research"
    """Web research synthesis.

    Scope: Synthesize web search results into actionable writing
    research. Combines multiple search results into coherent,
    story-relevant insights.
    Input: Search query, search results, project context.
    Output: Synthesized research summary.
    NOT: General chat (use CHAT). NOT: Analysis of existing text
    (use ANALYSE).
    """

    # ------------------------------------------------------------------
    # Embeddings (handled separately via embeddings.py)
    # ------------------------------------------------------------------

    EMBED = "embed"
    """Text embedding (not routed via gateway).

    Scope: Generate vector embeddings for text. Handled entirely by
    core/embeddings/ — does NOT go through the model routing cascade
    or the LLM gateway.
    Input: Text to embed.
    Output: Vector embedding.
    NOT: Routed through gateway. NOT: An LLM intent in the traditional sense.
    """
