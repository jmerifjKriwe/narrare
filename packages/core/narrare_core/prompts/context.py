"""
PromptContext — carries all variables needed to render any prompt.

Every LLM call in Narrare assembles a PromptContext first,
then passes it to the PromptComposer. No service builds prompts directly.

See CONSTRAINTS.md RULE-02.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

from narrare_core.context._kb_envelope import (
    OmissionReason,
    ProvenanceField,
    RenderedKBContext,
)


@dataclass(slots=True)
class KBContextEntry:
    """A single KB entry included in context.

    Metadata fields (source, evidence, confidence, review_status, freshness)
    track data provenance and quality for cross-feature coherence (CR-AUFG-04).
    """

    entity_type: str
    name: str
    content: str
    relevance_score: float = 1.0
    source: str = "manual"  # "manual" | "auto_extraction" | "imported" | "wiki_generated"
    evidence: str = ""  # Human-readable reason why this entry is relevant
    confidence: float = 1.0  # 0.0-1.0 confidence score for auto-extracted facts
    review_status: str = "endorsed"  # "pending" | "endorsed" | "rejected"
    freshness: str = "fresh"  # "fresh" | "stale" | "pending" — wiki/LLM summary freshness


def validate_world_context(world_context: str) -> list[str]:
    """Validate world_context has minimum required structure.

    Returns a list of warnings (empty list means the context looks OK).
    Never raises — all issues are reported as warnings per RULE-11.
    """
    warnings: list[str] = []

    if not world_context.strip():
        warnings.append("world_context is empty")
        return warnings

    # Heuristic: check for at least one entity-type keyword
    entity_keywords = (
        "character",
        "location",
        "faction",
        "setting",
        "timeline",
        "event",
        "relationship",
        "system",
        "object",
        "concept",
    )
    lower = world_context.lower()
    has_entity_keyword = any(kw in lower for kw in entity_keywords)

    # Heuristic: check for structured boundaries (headings, bullet lists,
    # or colon-separated labels like "Name: ...")
    has_structure = any(
        marker in world_context for marker in ("###", "##", "- ", "* ", ":", "\n\n")
    )

    if not has_entity_keyword and not has_structure:
        warnings.append(
            "world_context appears to be unstructured text without "
            "clear entity references or boundaries"
        )

    return warnings


@dataclass(slots=True)
class PromptContext:
    """
    All variables available for prompt rendering.

    Fields are optional — prompts declare which they require.
    Missing required variables raise PromptVariableError at compose time.
    """

    # --- Project metadata ---
    language: str = "en"
    writing_language: str = ""  # output language (freetext, e.g. "Schweizerdeutsch")
    project_title: str = ""
    genre: str = ""
    tone: str = ""
    story_structure: str = ""
    author_name: str = ""

    # --- Novel context ---
    # These fields are populated by ProjectWritingProfile when a project
    # context is available. See: FIND-007, core/project/profile.py.
    novel_synopsis: str = ""
    style_profile: str = ""

    # --- Chapter context ---
    mode: str = ""  # writing mode: new_chapter, extend, etc.
    chapter_title: str = ""
    existing_content: str = ""  # for extend/rewrite operations
    author_instructions: str = ""  # explicit instructions from the writer
    previous_chapter_summary: str = ""
    next_chapter_hint: str = ""

    # --- KB context ---
    kb_context_entries: list[KBContextEntry] = field(default_factory=list[KBContextEntry])
    kb_summary: str = ""  # compact list of all KB entities

    # --- Entity context (KB sessions) ---
    entity_type: str = ""
    entity_name: str = ""
    entity_current_content: str = ""
    entity_template: str = ""
    entity_focus_areas: str = ""

    # --- Analysis context ---
    text_to_analyse: str = ""
    analysis_focus: str = ""

    # --- Character voice profiles ---
    character_voice_profiles: str = ""  # Voice consistency data for dialogue generation

    # --- Memory / Preference context ---
    user_preferences: str = ""  # Formatted preference text from memory layer
    avoidance_patterns: str = ""  # Things the user dislikes (from feedback)
    style_constraints: str = ""  # Derived style constraints from feedback
    cross_session_context: str = ""  # Cross-session writing memories from mem0

    # --- Extra variables ---
    # For feature-specific variables not covered above.
    # Keys must be valid Python identifiers.
    extra: dict[str, Any] = field(default_factory=dict[str, Any])

    def as_variables(self) -> dict[str, str]:
        """
        Return all context fields as a flat string dict for variable substitution.

        Combines all dataclass fields with extra variables.
        Non-string values are converted to strings.
        """
        variables: dict[str, str] = {}

        for f in fields(self):
            if f.name == "extra":
                continue
            value = getattr(self, f.name)
            if isinstance(value, list):
                # Format KB entries as readable text block
                if value and isinstance(value[0], KBContextEntry):
                    rendered = self._format_kb_entries(value)  # pyright: ignore[reportUnknownArgumentType]
                    variables[f.name] = rendered.text
                else:
                    variables[f.name] = "\n".join(str(v) for v in value)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
            else:
                variables[f.name] = str(value) if value is not None else ""

        # Extra variables override dataclass fields
        for key, value in self.extra.items():
            variables[key] = str(value) if value is not None else ""

        # Fallback: writing_language defaults to language if not explicitly set
        if not variables.get("writing_language"):
            variables["writing_language"] = variables.get("language", "en")

        return variables

    @staticmethod
    def _format_kb_entries(entries: list[KBContextEntry]) -> RenderedKBContext:
        """Format KB entries as a readable text block for injection.

        Returns a :class:`RenderedKBContext` per ADR-050 P1-A
        (CR-AUFG-04-01). The wire format (``### Type: Name\\nContent``)
        is preserved unchanged — this is a provenance-accounting
        migration, not a wire-format change. There is no prompt
        regression: ``result.text`` is byte-for-byte identical to the
        pre-C2a ``str`` return value for the same input.

        **Provenance accounting (RULE-22):** ``KBContextEntry`` carries
        ``source``, ``evidence``, ``confidence``, ``review_status`` and
        ``freshness``. The compact immediate-context wire format renders
        none of these into the prompt. All are explicitly omitted with
        reason ``tier_does_not_require`` (the format is tier-1/tier-4
        immediate/suggested context where provenance is not rendered).
        Without this accounting the metadata was silently dropped at
        the render boundary — the gap ADR-050 P1-A closes.

        KBContextEntry provenance fields → ProvenanceField literals::

            source + confidence → "provenance" (combined source marker)
            evidence            → "evidence"
            review_status       → "review_state"
            freshness           → "freshness"

        ``priority`` and ``kb_lifecycle`` are not carried by
        ``KBContextEntry`` and therefore cannot be lost — they are not
        listed in ``omitted_fields``.
        """
        render_path = "narrare_core.prompts.context.PromptContext._format_kb_entries"
        if not entries:
            return RenderedKBContext(
                text="",
                preserved_fields=frozenset(),
                omitted_fields=(),
                entry_count=0,
                render_path=render_path,
            )
        parts: list[str] = []
        for entry in entries:
            parts.append(f"### {entry.entity_type.title()}: {entry.name}\n{entry.content}")

        omitted: tuple[tuple[ProvenanceField, OmissionReason], ...] = (
            ("provenance", "tier_does_not_require"),
            ("evidence", "tier_does_not_require"),
            ("review_state", "tier_does_not_require"),
            ("freshness", "tier_does_not_require"),
        )
        return RenderedKBContext(
            text="\n\n".join(parts),
            preserved_fields=frozenset(),
            omitted_fields=omitted,
            entry_count=len(entries),
            render_path=render_path,
        )
