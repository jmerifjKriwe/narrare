"""Chat prompt-context assembly and effective-message resolution.

Owns the context steps of the chat flow (RULE-04 extraction from
``chat_service``):
- :func:`build_prompt_context` builds the chat ``PromptContext``: the core
  chat context (project metadata — novel-backed when the conversation is
  project-linked, placeholders otherwise) plus the conversation history
  rendered into ``extra["conversation_history"]``.
- :func:`prepare_effective_context` composes the ADR-048 Mode 2 invocation
  and returns the enriched context that flows to ``ChatDeps`` — skipping
  project-correlated enrichment for project-less conversations (NOTES-001
  §6b: without a project there is nothing to correlate; graceful skip with
  a log, no error — RULE-11).
- :func:`resolve_effective_message` resolves the effective user message,
  prepending a requested scratchpad note as a runtime context block
  (NOTES-001 §6b — user-message channel, never a prompt template,
  RULE-02; graceful degradation on missing/unowned notes, RULE-11).
- :func:`resolve_owned_novel` resolves the caller-owned novel for a
  project-linked conversation (IDOR-hardened, notes ``_validate_link``
  semantics) so the context tier carries real novel metadata instead of
  placeholders (FO-7 follow-up).
- :func:`resolve_chat_kb_vars` resolves the chat template's per-type KB
  prompt variables (``kb_characters`` / ``kb_locations`` / ``kb_factions`` /
  ``kb_relationships`` bundle slots + the ``kb_other`` catch-all) through
  the canonical ``KBContextProviderProtocol`` (ADR-067) in a single
  unfiltered fetch per turn (#11): the provider partitions the fetch into
  the bundle's slots AND its ``other`` render, which the seam reads instead
  of a second ``fetch_entities`` call. Degrades to ``None`` (→ or-{} no-op
  spread, baseline placeholders stand) for unwired providers / project-less
  chat (RULE-11); the provider itself never raises.

Extracted from ``chat_service.py`` for RULE-04 (300-line service limit);
modularise, never compress. One responsibility (RULE-06): prepare the
effective chat context.

See:
    narrare_core.chat.chat_service_core.build_chat_context (core builder),
    ADR-024, ADR-045, ADR-048, ADR-067, NOTES-001 §6b,
    CONSTRAINTS.md RULE-02/RULE-04/RULE-06/RULE-07/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

from narrare_core.chat.chat_service_core import build_chat_context, format_history
from narrare_core.context._render_options import RenderOptions
from narrare_core.notes.contracts import format_note_context_block
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.notes.contracts import OwnedLinkLookupProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.chat.contracts import ChatMessage
    from narrare_core.notes.contracts import NoteLookupProtocol, NoteSnapshot
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)


@runtime_checkable
class NovelMetadataLike(Protocol):
    """Structural contract for the metadata the chat seam reads off a novel.

    The chat service resolves the owned novel through
    ``OwnedLinkLookupProtocol`` (whose ``get_owned`` is deliberately typed
    ``object | None`` to avoid a notes→novels type dependency). This
    protocol names the Backend-owned attribute subset (RULE-07) the chat
    context tier consumes; lookup results that do not provide it degrade
    to empty placeholders (RULE-11 — warn, never raise).
    """

    @property
    def title(self) -> str: ...

    @property
    def genre(self) -> str: ...


def _novel_metadata(novel: object | None) -> tuple[str, str]:
    """Extract ``(title, genre)`` from a lookup result, degrading to "".

    A ``None`` result (project-less chat or unwired lookup) and a
    non-novel-shaped result both yield the empty placeholders; the shape
    mismatch is logged (RULE-11 — never silent, never raised).
    """
    if novel is None:
        return "", ""
    if not isinstance(novel, NovelMetadataLike):
        logger.warning(
            "chat_novel_metadata_unavailable",
            novel_type=type(novel).__name__,
        )
        return "", ""
    return novel.title, novel.genre


def build_prompt_context(
    history: list[ChatMessage],
    novel: object | None = None,
    kb_vars: dict[str, str] | None = None,
) -> PromptContext:
    """Build the chat PromptContext with conversation history + novel metadata.

    Args:
        history: The conversation messages (oldest first) from the store.
        novel: The owned novel resolved for a project-linked conversation
            (single fetch reused from project-link validation), or ``None``
            for project-less chat / test contexts — the context then keeps
            the empty project-metadata placeholders (ADR-024 minimal tier).
        kb_vars: Canonical per-type KB prompt variables
            (:func:`resolve_chat_kb_vars`), spread over the core tier's
            defaults via ``**(kb_vars or {})`` — degradation (``None``)
            spreads nothing, so the documented-empty FO-7 placeholders stand.

    Returns:
        A PromptContext with ``extra["conversation_history"]`` populated,
        ``project_title`` / ``genre`` backed by the novel when available,
        and the per-type KB slots fed from ``kb_vars`` when resolved.
    """
    title, genre = _novel_metadata(novel)
    context = build_chat_context(
        project_title=title,
        genre=genre,
        language="en",
    )
    context.extra["conversation_history"] = format_history(history)
    # Canonical KB context (ADR-067): populated per-type renders override the
    # core tier's documented-empty placeholders. Degradation (kb_vars=None)
    # is a no-op spread — the or-{} convention, never literal "" keys.
    context.extra = {**context.extra, **(kb_vars or {})}
    return context


async def resolve_chat_kb_vars(
    *,
    kb_context_provider: KBContextProviderProtocol | None,
    novel_id: UUID | None,
) -> dict[str, str] | None:
    """Resolve the chat template's per-type KB prompt variables (ADR-067).

    Single fetch+render source for the slots the governed chat template
    carries: ``kb_characters`` / ``kb_locations`` / ``kb_factions`` /
    ``kb_relationships`` (the bundle's :meth:`~KBContextBundle.to_prompt_variables`
    mapping) plus ``kb_other`` — read from the bundle's partitioned ``other``
    render (single unfiltered fetch per turn, #11). Chat has no
    systems/timelines template vars, so those types must stay visible in
    ``kb_other`` (CR-AUFG-04-04); a pre-partition provider (``other is
    None``) degrades the catch-all to ``""`` (backward compatible).
    ``kb_suggested`` is deliberately NOT resolved here: its enricher is
    gated on a non-``None`` AdoptionPolicy (ruling pending), and the slot
    stays documented-empty.

    Non-writing consumer convention (planning/analysis seams): renders carry
    provenance annotations (``RenderOptions(annotate_provenance=True)``,
    FIND-017) consistently across all five slots.

    Args:
        kb_context_provider: The canonical provider, or ``None`` when not
            wired (test contexts only — production wiring always supplies
            it).
        novel_id: The project-linked novel whose KB is rendered, or
            ``None`` for project-less chat (NOTES-001 §6b — nothing to
            correlate, no fetch is performed).

    Returns:
        The five prompt variables ready for the ``**(kb_vars or {})``
        spread, or ``None`` when no provider is wired / the chat is
        project-less (the spread then keeps the baseline placeholders —
        RULE-11). The provider never raises (empty bundle / ``[]`` on
        failure), so an empty KB degrades to empty-slot values.
    """
    if kb_context_provider is None or novel_id is None:
        return None

    options = RenderOptions(annotate_provenance=True)
    # Single fetch per turn (#11): the provider fetches unfiltered once and
    # partitions — the bundle slots carry the per-type renders, ``other`` the
    # catch-all. Chat adds no seam-side budget; the render is bounded at the
    # core formatter's DEFAULT_MAX_ENTITIES count cap with an LLM-visible
    # omission marker at the provider's render (never a silent drop —
    # CR-AUFG-04-04). A pre-partition provider (``other is None``) degrades
    # ``kb_other`` to "" (backward compatible, RULE-11).
    bundle = await kb_context_provider.fetch_context(novel_id, options=options)
    kb_vars = bundle.to_prompt_variables()
    kb_vars["kb_other"] = bundle.other.text if bundle.other is not None else ""
    return kb_vars


async def resolve_owned_novel(
    *,
    novel_lookup: OwnedLinkLookupProtocol | None,
    project_id: UUID | None,
    user_id: UUID,
) -> object | None:
    """Resolve the caller-owned novel for a non-null project link.

    Notes ``_validate_link`` semantics (NOTES-001 ownership pattern):
    ``get_owned`` returns the entity only for its owner, so foreign and
    unknown novels are indistinguishable — both raise NotFoundError
    (→ HTTP 404, no enumeration oracle). ``novel_lookup is None`` (test
    contexts only; production wiring always provides it) skips the check.

    The returned novel feeds :func:`build_prompt_context` (its
    ``project_title`` / ``genre`` metadata) — the single ownership fetch
    is reused for context assembly, no extra query (FO-7 follow-up: the
    chat seam no longer holds zero novel data).

    Returns:
        The owned novel, or ``None`` when the check is skipped or the
        conversation is project-less.

    Raises:
        NotFoundError: The novel does not exist or is owned by another
            user.
    """
    if project_id is None or novel_lookup is None:
        return None
    novel = await novel_lookup.get_owned(project_id, user_id)
    if novel is None:
        raise NotFoundError("Novel", identifier=str(project_id))
    return novel


async def prepare_effective_context(
    *,
    invocation_pipeline: InvocationPipeline | None,
    prompt_ctx: PromptContext,
    user_id: UUID,
    project_id: UUID | None,
    conv_id: UUID,
    invocation_id: UUID,
) -> PromptContext:
    """Return the context for ``ChatDeps``, skipping enrichment when project-less.

    Runs ``compose_chat_invocation()`` (ADR-048 Mode 2) for correlated
    evidence + enrichment. NOTES-001 §6b: without a project there is
    nothing to correlate — pass no pipeline so ``compose_chat_invocation``
    takes its documented no-op path (backward compatible). The skip is
    logged, not raised (RULE-11: graceful degradation, no error).

    Args:
        invocation_pipeline: The InvocationPipeline, or ``None`` for a no-op.
        prompt_ctx: The original chat prompt context.
        user_id: The authenticated user's UUID (ADR-045 Decision 6).
        project_id: The project UUID for enrichment correlation, or
            ``None`` for project-less chat (NOTES-001 §6b).
        conv_id: The conversation UUID.
        invocation_id: The per-turn invocation UUID.

    Returns:
        The enriched ``PromptContext`` (or the original on failure / no-op).
    """
    from narrare.chat._invocation import compose_chat_invocation

    if project_id is None:
        logger.info(
            "chat_project_context_skipped",
            user_id=str(user_id),
            conversation_id=str(conv_id),
        )
    return await compose_chat_invocation(
        invocation_pipeline=invocation_pipeline if project_id is not None else None,
        prompt_ctx=prompt_ctx,
        user_id=user_id,
        project_id=project_id,
        conv_id=conv_id,
        invocation_id=invocation_id,
    )


async def resolve_effective_message(
    *,
    note_lookup: NoteLookupProtocol | None,
    note_id: UUID | None,
    message: str,
    user_id: UUID,
) -> str:
    """Resolve the effective user message with an optional note attached.

    NOTES-001 §6b: when the request carries a ``note_id``, the note snapshot
    is serialized via ``format_note_context_block`` (core contract) and
    prepended to the user message — RUNTIME INPUT in the user-message
    channel, never baked into a system/task template (RULE-02; same
    category as ``format_history``). A missing/unowned note (snapshot is
    ``None``) or an unwired lookup degrades gracefully: warn and proceed
    without the note (RULE-11 — no error mid-conversation).

    Args:
        note_lookup: ``NoteLookupProtocol`` implementation (the notes
            service, injected by wiring), or ``None`` when note injection
            is not wired.
        note_id: The note to attach, or ``None`` for plain chat (no
            lookup is performed then).
        message: The raw user message text.
        user_id: The authenticated user's UUID (ownership check).

    Returns:
        The effective message — ``"<note block>\\n\\n<message>"`` when a
        note was found, otherwise the original message unchanged.
    """
    if note_id is None:
        return message

    snapshot: NoteSnapshot | None = None
    if note_lookup is not None:
        snapshot = await note_lookup.get_note_snapshot(note_id, user_id)

    if snapshot is None:
        logger.warning(
            "chat_note_unavailable",
            note_id=str(note_id),
        )
        return message

    return f"{format_note_context_block(snapshot)}\n\n{message}"
