"""ANAL-007 Author Voice service contract — AuthorVoiceServiceProtocol.

The author-voice service orchestrates the ADR-074 hybrid pipeline
(deterministic :class:`VoiceMetricsAnalyzer.analyze_text` +
:class:`AuthorMetricsAnalyzer` + :class:`AuthorVoiceAgent`) over a novel's
selected chapters, persists the resulting
:class:`~narrare_core.profiles.author_voice.AuthorVoiceProfile` to
``ProjectSettings.author_voice`` (via
:class:`~narrare.analysis.author_voice_repository.AuthorVoiceRepository`), and
streams SSE events so the frontend can render progressively.

RULE-13 (ADR-065): :meth:`analyze` is the SSE ``AsyncIterator`` mirroring
:class:`CharacterVoiceService.analyze`. The Core
:class:`~narrare_core.agents.author_voice_agent.AuthorVoiceAgent` itself
exposes the non-streaming ``run()`` / streaming ``run_stream()`` pair; the
service uses ``run()`` (one structured-output call) because the profile is a
single object, not a token stream. The two-method contract is therefore
honoured at the layer where it applies (the agent), exactly as the spec's
RULE-13 compliance row records.

Prompt resolution is Mode 1 (composer-driven, ADR-054): the service resolves
its system prompt via :class:`PromptComposer` and the governed
``author_voice`` template (``LLMIntent.VOICE`` + ``context_mode=
"author_voice"``), then passes it to the
:class:`AuthorVoiceAgent` constructor. No inline f-string feature prompt is
assembled in the service (RULE-02 / RULE-02b).

See:
    :mod:`narrare.analysis.author_voice_service` — implementation.
    :mod:`narrare.analysis.schemas_author_voice` — SSE event + response models.
    :mod:`narrare.analysis.author_voice_repository` — storage (ADR-074).
    ADR-074 — Author Voice Storage Contract.
    ADR-055 — Character voice contract (the structural parallel mirrored here).
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.analysis.schemas_author_voice import AuthorVoiceStreamEvent
    from narrare_core.profiles.author_voice import AuthorVoiceProfile


@runtime_checkable
class AuthorVoiceServiceProtocol(Protocol):
    """Protocol for the ANAL-007 author-voice profiling service.

    Delegates to the Core-layer :class:`AuthorVoiceAgent` (pydantic-ai) which
    profiles the narrator's voice by interpreting the chapter prose together
    with the deterministic :class:`VoiceMetrics` (computed by
    :meth:`VoiceMetricsAnalyzer.analyze_text`) and :class:`AuthorMetrics`
    (computed by :class:`AuthorMetricsAnalyzer`) — one LLM call. The resulting
    descriptive fields are merged with the deterministic metrics into an
    :class:`AuthorVoiceProfile` and persisted via
    :class:`AuthorVoiceRepository` (no raw column access — ADR-074 binding).

    Prompt resolution is Mode 1 (composer-driven, ADR-054): the service
    resolves its system prompt via :class:`PromptComposer` and the governed
    ``author_voice`` template (``LLMIntent.VOICE``), then passes it to the
    :class:`AuthorVoiceAgent` constructor (pydantic-ai binds
    ``system_prompt`` at construction, not at run-time).
    """

    async def analyze(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID] | None,
        user_id: UUID,
    ) -> AsyncIterator[AuthorVoiceStreamEvent]:
        """Profile the author voice across selected chapters, streaming SSE events.

        Runs the ADR-074 hybrid pipeline (deterministic metrics + LLM
        qualitative profile) over the selected chapters' full prose
        (narration + dialogue together), assembles an
        :class:`AuthorVoiceProfile` (descriptive + metric groups), persists
        it to ``ProjectSettings.author_voice`` via the repository (bumping
        ``updated_at`` so freshness signals work), and yields a
        ``"progress"`` event, one ``"result"`` event carrying the assembled
        profile, then a terminal ``"done"`` event.

        The chapter prose + precomputed metrics flow as runtime data in the
        agent run prompt (user channel, RULE-02a category 3); the governed
        system prompt flows through :class:`PromptComposer` (Mode 1).

        RULE-11 graceful degradation:
            - No chapters / empty selection → terminal ``"done"`` with a
              progress message (no LLM call, no crash).
            - Below the 3-chapter minimum → a ``"progress"`` warning is
              surfaced but the analysis proceeds (soft warning, not a block;
              the panel may also block client-side).

        Args:
            novel_id: The novel whose chapters are analysed.
            chapter_ids: Specific chapters to analyse, or ``None`` / empty to
                analyse every chapter in the novel.
            user_id: The user requesting analysis (for access control).

        Yields:
            :class:`AuthorVoiceStreamEvent` instances: a ``"progress"``
            event, one ``"result"`` event carrying the profile, then a
            terminal ``"done"`` event (``is_final=True``).

        Raises:
            narrare_core.shared.errors.NotFoundError: If the novel or any
                selected chapter does not exist or is not accessible.
            narrare_core.shared.errors.ConfigurationError: If no
                ``PromptComposer`` is configured.
        """
        ...

    async def get_profile(
        self,
        novel_id: UUID,
        user_id: UUID,
    ) -> AuthorVoiceProfile | None:
        """Load the stored author-voice profile for a novel.

        Reads via :class:`AuthorVoiceRepository` (no raw column access).
        Returns ``None`` when no profile is stored (RULE-11 graceful
        degradation). The ``user_id`` is used for access control on the
        novel.

        Args:
            novel_id: The novel whose profile is loaded.
            user_id: The user requesting the profile (access control).

        Returns:
            The stored :class:`AuthorVoiceProfile`, or ``None`` when no
            profile exists yet.

        Raises:
            narrare_core.shared.errors.NotFoundError: If the novel does not
                exist or is not accessible by ``user_id``.
        """
        ...

    async def clear_profile(self, novel_id: UUID, user_id: UUID) -> None:
        """Clear the stored author-voice profile for a novel.

        Delegates to :meth:`AuthorVoiceRepository.clear` (sets the column to
        NULL). Used by the panel's "Delete profile" action to return to the
        default AI style. The ``user_id`` is used for access control on the
        novel.

        Args:
            novel_id: The novel whose profile is cleared.
            user_id: The user requesting the clear (access control).

        Raises:
            narrare_core.shared.errors.NotFoundError: If the novel does not
                exist or is not accessible by ``user_id``.
        """
        ...
