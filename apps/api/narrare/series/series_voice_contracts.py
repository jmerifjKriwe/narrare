"""Series Voice service contract — SeriesVoiceServiceProtocol (Spec 3 Task 2).

The series-voice service profiles one band's (novel's) narrator voice and
stores the result as ``SeriesSettings.author_voice`` (the Delta-model
foundation, ADR-078). It REUSES the existing ``AuthorVoiceAgent`` pipeline
(ANAL-007 / ADR-074) — the same helpers
(:func:`load_selected_chapters`, :func:`resolve_author_voice_prompt`,
:func:`run_author_voice_agent`, :func:`assemble_author_voice_profile`) that
:class:`~narrare.analysis.author_voice_service.AuthorVoiceService` uses at
novel level. No new agent is created (RULE-01b: agents are the LLM surface).

The only difference from novel-level author voice is the STORAGE TARGET:
``AuthorVoiceService`` persists to ``ProjectSettings.author_voice`` (novel
1:1); this service persists to ``SeriesSettings.author_voice`` (series 1:1)
via :meth:`SeriesRepository.update_settings` (no raw column access, RULE-07).

Ownership contract (C1 / anti-enumeration — mirrors
``SeriesService._verify_series_ownership``): every method takes ``user_id``
and verifies the caller owns the series BEFORE any read/mutation. A *missing*
series and a *not-owned* series BOTH surface as ``ForbiddenError`` (HTTP 403)
— never ``NotFoundError`` (404) — so series ids are not enumerable. The
profile method additionally verifies the novel belongs to the series.

A separate Protocol file (not appended to ``series/contracts.py``) keeps the
197-line ``contracts.py`` under the RULE-04 file-size limit and keeps
series-voice concerns self-contained (RULE-06: one responsibility per file).
Mirrors the ``band_summary_contracts.py`` extraction precedent.

See:
    :mod:`narrare.series.series_voice_service` — implementation.
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — Author Voice Storage Contract (the pipeline reused).
    CONSTRAINTS.md RULE-03 / RULE-06 / RULE-07 / RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.profiles.author_voice import AuthorVoiceProfile


@runtime_checkable
class SeriesVoiceServiceProtocol(Protocol):
    """Protocol for the Spec 3 series-voice profiling + management service.

    Four operations back the Series Voice API (Task 3):

    - ``profile_from_novel`` — verify novel in series → fetch chapters → run
      the existing ``AuthorVoiceAgent`` pipeline → store the assembled
      :class:`AuthorVoiceProfile` as ``SeriesSettings.author_voice``.
    - ``get`` — load the current series voice profile (``None`` when empty).
    - ``update_override`` — store a user-supplied profile dict (manual
      override; validated as :class:`AuthorVoiceProfile`).
    - ``clear_override`` — null ``SeriesSettings.author_voice``.

    All dependencies are injected (RULE-07). Ownership is verified inside the
    service (mirrors :class:`SeriesService`) so the contract is enforced even
    when called from non-request contexts.
    """

    async def profile_from_novel(
        self,
        series_id: UUID,
        novel_id: UUID,
        user_id: UUID,
    ) -> AuthorVoiceProfile:
        """Profile a novel's narrator voice → store as series author_voice.

        Runs the ADR-074 hybrid pipeline (deterministic metrics + the existing
        ``AuthorVoiceAgent``) over the novel's full chapter prose, assembles an
        :class:`AuthorVoiceProfile`, and persists it to
        ``SeriesSettings.author_voice`` via
        :meth:`SeriesRepository.update_settings` (RULE-07: no raw column
        access).

        Args:
            series_id: The series whose voice is being profiled.
            novel_id: The novel (band) whose prose is analysed. MUST belong to
                ``series_id`` (else ``ForbiddenError``).
            user_id: The caller (ownership verified, anti-enumeration).

        Returns:
            The assembled + persisted :class:`AuthorVoiceProfile`.

        Raises:
            narrare_core.shared.errors.ForbiddenError: Series missing/not
                owned by ``user_id``, or novel not in ``series_id`` (403,
                anti-enumeration — never 404).
            narrare_core.shared.errors.ValidationError: The novel has no
                chapters with prose to profile (RULE-11: fail fast, no
                hallucinated profile).
            narrare_core.shared.errors.NotFoundError: No model config
                resolved for the analysis category.
            narrare_core.shared.errors.ConfigurationError: No
                ``PromptComposer`` configured.
        """
        ...

    async def get(
        self,
        series_id: UUID,
        user_id: UUID,
    ) -> AuthorVoiceProfile | None:
        """Load the stored series voice profile.

        Returns ``None`` when no profile is stored (RULE-11 graceful
        degradation — generation renders empty ``{{author_voice}}``).

        Raises:
            narrare_core.shared.errors.ForbiddenError: Series missing/not
                owned by ``user_id`` (403, anti-enumeration).
        """
        ...

    async def update_override(
        self,
        series_id: UUID,
        user_id: UUID,
        override: dict[str, object],
    ) -> AuthorVoiceProfile:
        """Store a user-supplied voice profile (manual override).

        The dict is validated as :class:`AuthorVoiceProfile` for type safety
        before persisting. Replaces any existing profile (auto-profiled or
        previous override) — ``SeriesSettings`` has a single
        ``author_voice`` column.

        Raises:
            narrare_core.shared.errors.ForbiddenError: Series missing/not
                owned by ``user_id``.
            narrare_core.shared.errors.ValidationError: The override dict is
                not a valid :class:`AuthorVoiceProfile`.
        """
        ...

    async def clear_override(self, series_id: UUID, user_id: UUID) -> None:
        """Null ``SeriesSettings.author_voice`` (returns to "no series voice").

        Raises:
            narrare_core.shared.errors.ForbiddenError: Series missing/not
                owned by ``user_id``.
        """
        ...
