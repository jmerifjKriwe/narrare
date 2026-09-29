"""KB-context provider contracts — bundle value type + provider Protocol (ADR-067).

Extracted from ``contracts.py`` to respect the 200-line contracts file-size
limit (RULE-04). Holds the reusable KB-context surface: the per-novel
:class:`KBContextBundle` value type and the
:class:`KBContextProviderProtocol` every non-writing KB-consuming feature
populates its prompt from.

Core owns the vocabulary (``RenderedKBContext`` / ``RenderOptions``); this
value type + Protocol live in Backend because they group Backend-owned
per-type slots (RULE-07).

Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from narrare_core.context._kb_envelope import RenderedKBContext
from narrare_core.context._render_options import RenderOptions

if TYPE_CHECKING:
    import uuid

    from narrare.kb.models import KBEntry


def _empty_rendered() -> RenderedKBContext:
    """Build an empty ``RenderedKBContext`` (degradation sentinel, ADR-050)."""
    return RenderedKBContext(
        text="",
        preserved_fields=frozenset(),
        omitted_fields=(),
        entry_count=0,
        render_path="narrare.kb.context_contracts.KBContextBundle.empty",
    )


@dataclass(frozen=True, slots=True)
class KBContextBundle:
    """Canonical per-type rendered KB context for one novel (ADR-067).

    Every non-writing KB-consuming feature populates its prompt from this
    bundle. Each field is an ADR-050 :class:`RenderedKBContext`
    (``.text`` = prompt-bound string; ``preserved_fields`` / ``omitted_fields``
    = provenance accounting, RULE-22).

    The bundle is produced by :class:`KBContextProviderProtocol.fetch_context`.
    Core owns the vocabulary (``RenderedKBContext`` / ``RenderOptions``); this
    value type lives in Backend because it groups Backend-owned per-type slots
    (RULE-07).

    ``other`` is the optional catch-all render of every entity type outside
    the named slots (chat's ``kb_other`` source). It is ``None`` when the
    non-slot types were not part of the fetch scope: degradation bundles,
    ``fetch_context`` calls with an explicit ``entity_types`` filter, or
    providers predating the single-fetch partition. ``None`` means absent,
    not empty.
    """

    characters: RenderedKBContext
    locations: RenderedKBContext
    factions: RenderedKBContext
    relationships: RenderedKBContext
    render_options: RenderOptions
    other: RenderedKBContext | None = None

    @staticmethod
    def empty(options: RenderOptions | None = None) -> KBContextBundle:
        """Return a bundle of empty renderings (RULE-11 graceful degradation).

        Used when no provider is wired, the KB is empty, or the repository is
        unavailable — every consumer must still be able to compose its prompt.
        ``.to_prompt_variables()`` therefore yields ``""`` for every slot.
        """
        empty_ctx = _empty_rendered()
        return KBContextBundle(
            characters=empty_ctx,
            locations=empty_ctx,
            factions=empty_ctx,
            relationships=empty_ctx,
            render_options=options or RenderOptions(),
        )

    def to_prompt_variables(self) -> dict[str, str]:
        """Map the bundle to the registered KB prompt variables.

        Returns a dict keyed by ``kb_characters`` / ``kb_locations`` /
        ``kb_factions`` / ``kb_relationships`` ready for
        ``PromptContext(extra=...)``. Values are the rendered ``.text`` of each
        per-type :class:`RenderedKBContext` (empty string on degradation).
        """
        return {
            "kb_characters": self.characters.text,
            "kb_locations": self.locations.text,
            "kb_factions": self.factions.text,
            "kb_relationships": self.relationships.text,
        }


@runtime_checkable
class KBContextProviderProtocol(Protocol):
    """Single source for canonical KB prompt context (ADR-067).

    Fetches KB entries, renders per entity type through the ADR-050 envelope
    (``format_entities``), and returns a ready-to-inject
    :class:`KBContextBundle`. Replaces ad-hoc fetch/format helpers across
    planning and analysis. ``fetch_world_context`` succeeds
    ``kb/_world_context.py`` (same ``- name (type): brief`` wire format —
    preserves ``validate_world_context`` compatibility for kb merge/extract).

    Graceful degradation (RULE-11): an unavailable repository or empty KB
    yields empty renderings (``.text == ""``) — never an exception — so a
    feature always composes its prompt. Provenance flows through
    :class:`RenderOptions` (FIND-017): non-writing features get the same
    honest inline rendering as writing when ``annotate_provenance=True``.
    """

    async def fetch_context(
        self,
        novel_id: uuid.UUID,
        *,
        entity_types: list[str] | None = None,
        options: RenderOptions | None = None,
    ) -> KBContextBundle:
        """Fetch KB entities once and render them per-type into a bundle.

        Single unfiltered fetch per call: the novel's KB entities are fetched
        once and partitioned — the named slot types (character/location/
        faction) render into the bundle's slots (relationships render from
        the relationship repository), every other entity type renders into
        :attr:`KBContextBundle.other`, the catch-all for consumers without
        dedicated per-type template vars (e.g. chat's ``kb_other``).

        Args:
            novel_id: Novel whose KB entities are rendered.
            entity_types: Optional filter. When given, the fetch is restricted
                to these types and ``other`` stays ``None`` — the caller owns
                the type scope (pre-partition behavior). Omit it to get slots
                + ``other`` from the one fetch.
            options: Per-invocation render controls; pass
                ``RenderOptions(annotate_provenance=True)`` to carry
                provenance accounting onto the bundle.

        Returns:
            A :class:`KBContextBundle`. Never raises — degrades to
            :meth:`KBContextBundle.empty` on any repository failure.
        """
        ...

    async def fetch_entities(
        self,
        novel_id: uuid.UUID,
        *,
        entity_types: list[str] | None = None,
    ) -> list[KBEntry]:
        """Fetch the novel's raw KB entries (ADR-067 single KB source).

        Returns the persisted :class:`~narrare.kb.models.KBEntry` records so
        consumers that need entity-level data — e.g. resolving extracted names
        to real entity links for ``TimelineEvent.character_refs`` /
        ``location_ref`` (§7 follow-up) — reuse the provider's fetch instead of
        wiring a second KB repository. ``fetch_context`` renders these same
        records into prompt text; this method exposes the records themselves.

        Args:
            novel_id: Novel whose KB entries are fetched.
            entity_types: Optional entity-type filter.

        Returns:
            The novel's KB entries. Never raises — degrades to ``[]`` on any
            repository failure or when no repository is wired (RULE-11), so a
            consumer always proceeds (e.g. with empty refs).
        """
        ...

    async def fetch_world_context(
        self,
        novel_id: uuid.UUID,
        *,
        entity_type: str | None = None,
        max_entries: int = 30,
    ) -> str:
        """Aggregate compact world context for kb merge/extract.

        Succeeds ``kb/_world_context.py``: same ``- name (type): brief`` wire
        format (validated by ``validate_world_context``). Returns ``""`` on an
        unavailable repository or empty KB (RULE-11).
        """
        ...
