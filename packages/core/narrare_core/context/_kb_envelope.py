"""KB Context Envelope contract — provenance-preserving render boundary.

Defines the contract (ADR-050 P1-A — CR-AUFG-04-01) that every
KB-context render path MUST satisfy: provenance metadata must either
be preserved in the rendered text OR explicitly omitted with a
documented rationale. Silent loss of provenance is a RULE-22 violation.

This module was extracted from ``context/contracts.py`` to respect
RULE-04 (file size) and RULE-06 (one responsibility per file). The
types are re-exported from ``contracts.py`` for public API stability.

Root cause this contract closes: ``KBContextEntry`` and ``KBEntity``
both carry provenance fields (``source``, ``evidence``, ``confidence``,
``review_status``, ``freshness``, ``status``). But every render path
emits only ``### Type: Name\\nContent`` — provenance is silently
dropped at the boundary where the LLM consumes the context. The LLM
cannot reason about what it never receives, and downstream features
(CONS-001, Context Inspector, audit reports) cannot trace which facts
were authoritative vs inferred.

The Protocol is a contract (not a dataclass) because there are multiple
legitimate render strategies (tier-aware, token-budget-aware,
locale-aware). All of them must satisfy the same semantic contract:
prove provenance or prove it was deliberately omitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

#: Fields that constitute KB provenance. Anything outside this set is
#: content (e.g. ``content``, ``name``) and is always preserved.
type ProvenanceField = Literal[
    "priority",
    "provenance",  # source + evidence combined marker
    "review_state",
    "freshness",
    "evidence",
    "kb_lifecycle",  # draft | reviewed | canon | deprecated
]


#: Reasons a render path may legitimately omit a provenance field.
#: Anything outside this set is an undocumented omission and a RULE-22
#: violation. The string form is machine-readable so audit tooling can
#: compare render paths.
type OmissionReason = Literal[
    "token_budget_exhausted",
    "tier_does_not_require",  # e.g. tier-1 immediate context
    "consumer_cannot_act",  # e.g. raw SSE streaming where metadata is in header
    "explicitly_suppressed_for_run",  # per-invocation suppression with user approval
]


@runtime_checkable
class KBContextSource(Protocol):
    """Structural shape every renderable KB entry must satisfy.

    Both :class:`narrare_core.prompts.context.KBContextEntry` and
    :class:`narrare_core.writing.context_models.KBEntity` already
    satisfy this Protocol structurally. The Protocol exists so the
    :class:`KBContextEnvelope.render` signature can name a concrete
    type instead of ``Any`` (RULE-09).

    Concrete source types are free to carry additional fields beyond
    this shape; renderers may opt to use them.
    """

    entity_type: str
    name: str
    content: str
    source: str
    review_status: str
    confidence: float


@runtime_checkable
class KBContextEnvelope(Protocol):
    """Contract for rendering KB entries into prompt-bound text.

    Every code path that converts a list of KB entities/entries into a
    prompt variable string (``kb_characters``, ``kb_locations``,
    ``kb_pinned``, ``kb_suggested``, ``kb_timelines``, ``kb_systems``,
    ``kb_factions``, ``kb_context_entries``, ``kb_summary``) MUST
    implement this Protocol. The contract is:

    1. **Preserve-or-document**: For each ``ProvenanceField`` the
       render output either contains the field's value, or
       ``omitted_fields`` lists the field with an ``OmissionReason``.
    2. **Tier fidelity**: Renderings used in higher-priority tiers
       (Tier 3 referenced, Tier 5 pinned) MUST preserve all fields.
       Lower tiers MAY omit fields under documented reasons.
    3. **Existing tier-specific formats preserved**: This Protocol
       does not prescribe a wire format. Existing formats
       (``### Type: Name\\nContent``, wiki-compressed
       ``### Type: Name\\nNarrativeSummary``, pinned bypass) remain
       valid; what changes is that each render function MUST declare
       which provenance fields it preserves or omits.

    The Protocol is consumed by:

    * ``PromptContext._format_kb_entries`` (prompts/context.py)
    * ``WritingContextAssembler.format_entities`` /
      ``format_entities_with_wiki`` / Tier-3 processor
      (writing/_helpers.py, writing/context_wiki.py,
      writing/_tier3_processor.py)
    * ``ProactiveContextService`` (context/service.py)
    * ``extract_voice_profiles`` (writing/_voice_profiles.py) for the
      character_voice_profiles variable
    * ``TimelineEventEnvelope`` renderers in consistency pipeline
      (already compliant — ADR-044)

    Implementations live in core modules (RULE-07). App-layer services
    inject the chosen render strategy via DI; they MUST NOT assemble
    their own compact text format with hand-rolled provenance stripping
    (RULE-22 §1, §2).
    """

    def render(
        self,
        entries: list[KBContextSource],
        *,
        tier: str,
    ) -> RenderedKBContext:
        """Render KB entries into a prompt-bound text block.

        Args:
            entries: Source entities/entries satisfying
                :class:`KBContextSource`. Implementations may narrow
                further (e.g. require the ``KBEntity`` shape with
                ``similarity_score``); they document the narrowing in
                their docstring.
            tier: Tier identifier controlling fidelity. Recognised
                values: ``"tier1_immediate"``, ``"tier3_referenced"``,
                ``"tier4_suggested"``, ``"tier5_pinned"``,
                ``"proactive_suggestion"``, ``"voice_profile"``,
                ``"timeline_envelope"``. Unknown tier strings are
                treated as ``"tier4_suggested"`` (medium fidelity).

        Returns:
            A :class:`RenderedKBContext` with the text block and a
            provenance accounting of what was preserved or omitted.
        """
        ...


@dataclass(frozen=True, slots=True)
class RenderedKBContext:
    """Result of rendering KB entries via a :class:`KBContextEnvelope`.

    Attribute ``text`` is what gets injected into the prompt template
    via the variable engine (RULE-02). Attributes ``preserved_fields``
    and ``omitted_fields`` are audit metadata — they are NOT injected
    into the prompt unless an audit consumer explicitly requests them
    (e.g. Context Inspector, consistency evidence).

    Attributes:
        text: The rendered prompt-bound text. Empty string when no
            entries were provided.
        preserved_fields: Provenance fields whose values appear in
            ``text``. Subset of ``ProvenanceField`` literals.
        omitted_fields: Provenance fields whose values were stripped,
            each paired with an :class:`OmissionReason`. May be empty
            (high-fidelity tiers preserve everything).
        entry_count: Number of source entries rendered. Used for
            metadata accounting in ``ContextMetadata``.
        render_path: Human-readable identifier of the rendering code
            path (e.g. ``"writing._helpers.format_entities"``).
            Required so audit reports can correlate omissions to the
            function that produced them.
    """

    text: str
    preserved_fields: frozenset[ProvenanceField]
    # Tuples of (field, reason) — immutable so the dataclass stays hashable
    # and the Protocol return value stays safe to share across consumers.
    omitted_fields: tuple[tuple[ProvenanceField, OmissionReason], ...] = ()
    entry_count: int = 0
    render_path: str = ""

    def __str__(self) -> str:
        """Return the prompt-bound text for string contexts."""
        return self.text

    def __contains__(self, value: str) -> bool:
        """Return whether *value* appears in the prompt-bound text."""
        return value in self.text

    def split(self, sep: str | None = None, maxsplit: int = -1) -> list[str]:
        """Split the prompt-bound text.

        This preserves compatibility for legacy tests/callers that used
        renderer outputs as plain strings while production consumers move
        to explicit ``.text`` access.
        """
        return self.text.split(sep, maxsplit)
