"""Helper functions for the writing context assembler.

Extracted from ``context_assembler.py`` for RULE-04 compliance.
Contains frontmatter reference extraction and entity text formatting.

These are pure data transformations — no I/O, no DB, no LLM calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.context._kb_envelope import OmissionReason, ProvenanceField, RenderedKBContext
from narrare_core.context._provenance_annotation import (
    ProvenanceAnnotation,
    compute_provenance_annotation,
    merge_rendered_fields,
)
from narrare_core.shared.frontmatter import parse_frontmatter

if TYPE_CHECKING:
    from narrare_core.context._render_options import RenderOptions
    from narrare_core.writing.context_models import KBEntity
    from narrare_core.writing.models import WritingContext


_REFERENCE_KEYS: frozenset[str] = frozenset(
    {
        "pov_character",
        "characters",
        "location",
        "locations",
        "faction",
        "factions",
        "system",
        "systems",
        "timeline",
        "timelines",
    }
)


def extract_frontmatter_references(frontmatter: str) -> set[str]:
    """Extract entity IDs referenced in chapter frontmatter.

    Looks for keys: ``pov_character``, ``characters``, ``location``,
    ``locations``, ``faction``, ``factions``, ``system``, ``systems``,
    ``timeline``, ``timelines``.  Returns a set of entity ID strings.
    Returns an empty set for empty or unparsable input.
    """
    if not frontmatter.strip():
        return set()

    parsed = parse_frontmatter(frontmatter)
    if not parsed.has_frontmatter:
        return set()

    ids: set[str] = set()
    for key in _REFERENCE_KEYS:
        value = parsed.metadata.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            for item in value:  # pyright: ignore[reportUnknownVariableType]
                if item is not None:
                    ids.add(str(item))  # pyright: ignore[reportUnknownArgumentType]
        else:
            ids.add(str(value))  # pyright: ignore[reportUnknownArgumentType]
    return ids


def optional_block(label: str, text: str) -> str:
    """Wrap populated tier text in a value-side labelled block (T1a).

    Returns ``""`` when ``text`` is empty so plain variable substitution
    renders byte-identically for KB-empty novels.  For populated tiers the
    label lives on the value side (never in templates) and adds no ``### ``
    markers, so :meth:`WritingContext.to_metadata` entry counts (which
    count ``### `` headings) stay unchanged.
    """
    if not text:
        return ""
    return "\n\n" + label + ":\n" + text


def word_target_line(value: int | None, *, label: str) -> str:
    """Build the full word-target prompt line (label-in-value, Item F).

    Root-cause pattern per the Tier-5 / ADR-050 P1-D ``optional_block``
    precedent: the label lives in the VALUE, not in the template, so an
    empty target cannot leave a dangling label in the render. The leading
    newline is the append-to-previous-line convention — the placeholder
    sits at the end of the previous template line, so:

    - empty value → ``""`` → renders byte-identically to a template without
      the line at all (no blank line, no dangling label);
    - populated → ``"\\n<label>N"`` → reproduces the former static-label
      bullet layout byte-for-byte.

    ``label`` carries the per-template phrasing (review:
    ``"- Word target: "``, scene_by_scene: ``"Word target per scene: "``).
    Promoted from ``writing_graph_prompts._word_target_line`` as the shared
    supplier-side SSOT (slice 1 of the word_target label-in-value
    migration).
    """
    if not value:
        return ""
    return f"\n{label}{value}"


def context_bullet(value: str, label: str) -> str:
    """Build a full leading Context bullet (label-in-value).

    The template placeholder starts a line, so a populated value carries
    the bullet label plus a trailing newline (``"- Genre: Fantasy\\n"``)
    and an empty value renders ``""`` — byte-identical to a template
    without the bullet, so an unset value can never leave a dangling
    label. Label phrasing is per-template.
    """
    if not value:
        return ""
    return f"{label}{value}\n"


_KB_CONTEXT_EXTRA_FIELDS: tuple[str, ...] = (
    "kb_characters",
    "kb_locations",
    "kb_factions",
    "kb_other",
    "kb_relationships",
    "kb_suggested",
    "kb_systems",
    "kb_timelines",
    "kb_pinned",
    "kb_context_warnings",
)


def kb_context_extras(context: WritingContext) -> dict[str, str]:
    """Extract the ten KB prompt variables from a writing context.

    Single source of truth for the KB extras that writing-route prompt
    invocations (extend / rewrite / co_author / scene_by_scene) splice
    into their variable payloads.  ``None``-valued fields coalesce to
    ``""`` (mirroring the ``WritingContext`` defaults) so templates never
    see ``None``.  Pure transformation — no I/O.
    """
    return {name: getattr(context, name) or "" for name in _KB_CONTEXT_EXTRA_FIELDS}


_COMPACT_ENTITY_OMISSIONS: tuple[tuple[ProvenanceField, OmissionReason], ...] = (
    ("priority", "tier_does_not_require"),
    ("provenance", "tier_does_not_require"),
    ("review_state", "tier_does_not_require"),
    ("freshness", "tier_does_not_require"),
    ("kb_lifecycle", "tier_does_not_require"),
)


def format_entities(
    entities: list[KBEntity], *, options: RenderOptions | None = None
) -> RenderedKBContext:
    """Format entities as a readable text block with provenance accounting.

    The prompt-bound text remains the historical compact format:
    ``### Type: Name\\nContent``. ADR-050 P1-A accounting is carried in
    the returned :class:`RenderedKBContext` so metadata loss is explicit.

    When ``options.annotate_provenance`` is ``True`` (opt-in), uncertain
    entries receive an inline provenance bracket on the header line and
    the rendered :class:`ProvenanceField` literals are moved from
    ``omitted_fields`` to ``preserved_fields`` (RULE-22). When ``options``
    is ``None`` (default) the output is byte-for-byte identical to the
    pre-annotation behaviour.
    """
    render_path = "narrare_core.writing._helpers.format_entities"
    if not entities:
        return RenderedKBContext(
            text="",
            preserved_fields=frozenset(),
            omitted_fields=(),
            entry_count=0,
            render_path=render_path,
        )

    annotate = options is not None and options.annotate_provenance
    parts: list[str] = []
    annotations: list[ProvenanceAnnotation] = []
    for entity in entities:
        header = f"### {entity.entity_type.title()}: {entity.name}"
        if annotate:
            ann = compute_provenance_annotation(
                source=entity.source,
                confidence=entity.confidence,
                review_status=entity.review_status,
                freshness=entity.wiki_status or "",
            )
            annotations.append(ann)
            if ann.bracket is not None:
                header = f"{header} {ann.bracket}"
        parts.append(f"{header}\n{entity.content}")

    if annotate:
        return _build_accounted_result(
            parts, annotations, _COMPACT_ENTITY_OMISSIONS, len(entities), render_path
        )

    return RenderedKBContext(
        text="\n\n".join(parts),
        preserved_fields=frozenset(),
        omitted_fields=_COMPACT_ENTITY_OMISSIONS,
        entry_count=len(entities),
        render_path=render_path,
    )


def _build_accounted_result(
    parts: list[str],
    annotations: list[ProvenanceAnnotation],
    base_omissions: tuple[tuple[ProvenanceField, OmissionReason], ...],
    entry_count: int,
    render_path: str,
) -> RenderedKBContext:
    """Build a RenderedKBContext with RULE-22 accounting adjusted for
    provenance fields that were actually rendered into the bracket.

    Fields rendered for ANY entry in the batch move from ``omitted_fields``
    to ``preserved_fields``; the rest stay omitted with their existing
    :class:`OmissionReason`.
    """
    preserved = merge_rendered_fields(annotations)
    omitted: list[tuple[ProvenanceField, OmissionReason]] = [
        (field, reason) for field, reason in base_omissions if field not in preserved
    ]
    return RenderedKBContext(
        text="\n\n".join(parts),
        preserved_fields=preserved,
        omitted_fields=tuple(omitted),
        entry_count=entry_count,
        render_path=render_path,
    )
