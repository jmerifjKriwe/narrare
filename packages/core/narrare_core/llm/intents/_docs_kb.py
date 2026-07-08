"""Verbatim intent documentation — Knowledge base operations category.

Full original docstring text (Scope/Input/Output/NOT) for entity
creation, improvement, and extraction intents. Aggregated into
:data:`narrare_core.llm.intents.INTENT_DOCS`.

Split out of the former monolithic ``intents.py`` per RULE-04. The text
here is preserved word-for-word from the original member docstrings.
"""

from __future__ import annotations

from narrare_core.llm.intents._enums import LLMIntent

KB_INTENT_DOCS: dict[LLMIntent, str] = {
    LLMIntent.KB_CREATE: """\
Interactive KB entity creation via structured interview.

Scope: Guides author through creating a new KB entity by asking
structured questions about template fields. Builds entity field
by field through dialogue.
Input: {{template_structure}}, {{world_context}}, author answers.
Output: JSON with completed entity fields or draft with progress.
NOT: Fill a single field suggestion (use KB_SUGGEST).
NOT: Bulk entity enhancement (use KB_ENHANCE).
""",
    LLMIntent.KB_IMPROVE: """\
KB entry improvement analysis.

Scope: Analyzes an existing KB entry and identifies specific,
actionable improvement opportunities. Does NOT generate content —
identifies what is missing or weak.
Input: {{entity_type}}, {{template_structure}}, {{entry_content}},
{{existing_relationships}}, {{world_context}}.
Output: JSON with suggestions (add_field/connect/expand/reorganize),
completeness_score, overall_assessment.
NOT: Content generation (use KB_ENHANCE). NOT: Contradiction checking
(use KB_CONSISTENCY). NOT: Single-field suggestion (use KB_SUGGEST).
""",
    LLMIntent.KB_EXTRACT: """\
Extract entities from chapter text.

Scope: Scans chapter prose for new entities, entity updates,
relationships, and conflicts with existing KB data.
Input: Chapter text, {{existing_entity_names}}, {{chapter_title}}.
Output: JSON with extraction items (new_entity/update_entity/
relationship/conflict) with confidence scores and source quotes.
NOT: Interactive entity creation (use KB_CREATE).
NOT: Entity enhancement (use KB_ENHANCE).
""",
    LLMIntent.KB_INTERVIEW: """\
Ask the author a single focused question about a KB field.

Scope: One-question-at-a-time interview mode. Picks the most
important unanswered template field and asks the author about it.
Input: {{template_structure}}, {{existing_answers}}, {{world_context}}.
Output: JSON with mode="question", field_key, question text.
NOT: Suggest a value (use KB_SUGGEST). NOT: Bulk generation (use KB_ENHANCE).
NOT: Full entity creation flow (use KB_CREATE).
""",
    LLMIntent.KB_SUGGEST: """\
Suggest a well-reasoned value for a specific KB template field.

Scope: Single-field suggestion mode. Given a target field and
existing context, proposes the best value with justification.
Input: {{template_structure}}, {{existing_answers}}, {{world_context}},
{{target_field}}, {{target_field_description}}.
Output: JSON with mode="suggestion", field_key, suggested value,
reasoning, context_used.
NOT: Ask the author a question (use KB_INTERVIEW).
NOT: Improve the whole entry (use KB_IMPROVE).
""",
    LLMIntent.KB_ENHANCE: """\
Generate or expand a KB entity entry with multiple fields.

Scope: Bulk entity generation. Fills multiple template fields at
once based on partial existing answers and world context. Can
produce complete entries or drafts.
Input: {{entity_type}}, {{template_structure}}, {{existing_answers}},
{{world_context}}.
Output: JSON with mode (complete|draft), entry fields, reasoning,
progress score.
NOT: Single-field suggestion (use KB_SUGGEST).
NOT: Interactive interview (use KB_INTERVIEW or KB_CREATE).
""",
    LLMIntent.KB_WORLDBUILD: """\
Worldbuilding analysis — gap detection, connections, consistency.

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
""",
    LLMIntent.KB_CONSISTENCY: """\
KB entry-internal consistency checking.

Scope: ENTITY-level consistency. Checks a single KB entry for
internal field contradictions — cross-field values that logically
conflict within the same entry.
Input: {{entity_type}}, {{template_structure}}, {{entry_content}}.
Output: JSON with issues (critical/major/minor), suggested resolutions.
NOT: Cross-chapter consistency (use CONSISTENCY).
NOT: Cross-entity worldbuilding consistency (use KB_WORLDBUILD phase2).
""",
}
