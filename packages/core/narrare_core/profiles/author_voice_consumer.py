"""AuthorVoiceConsumer Protocol — generation-side author-voice contract.

Extracted from :mod:`narrare_core.profiles.contracts` (RULE-04: the parent
file exceeded the 200-line hard limit once Spec 3 / ADR-078 added the
``resolve_for_generation`` Delta-model method). Mirrors the
``series_voice_contracts.py`` extraction precedent (a contract split out to
keep its origin file under the size limit while keeping the concern
self-contained, RULE-06).

This module defines ONLY the :class:`AuthorVoiceConsumer` Protocol. The
producer/consumer voice-profile contracts
(:class:`VoiceProfileProvider`, :class:`VoiceProfileConsumer`) remain in
:mod:`narrare_core.profiles.contracts`.

See:
    ADR-074 — Author Voice Storage Contract (novel-scoped profile shape).
    ADR-078 — Series Voice Hierarchy (Delta model, opt-out).
    ADR-055 / ADR-057 — descriptive/metric boundary preserved here.
    CONSTRAINTS.md RULE-03 / RULE-06 / RULE-07 / RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.profiles.author_voice import AuthorVoiceProfile


@runtime_checkable
class AuthorVoiceConsumer(Protocol):
    """Consumer-side contract for author-voice data (ADR-074 / ANAL-007,
    extended by Spec 3 / ADR-078 for the Series Voice Hierarchy).

    Parallel to :class:`~narrare_core.profiles.contracts.VoiceProfileConsumer`,
    but for the AUTHOR voice (the narrator's prose voice). Two storage scopes
    cooperate under the Delta model (Spec 3):

    - Novel-scoped profile → ``ProjectSettings.author_voice`` JSONB (ADR-074).
    - Series-scoped profile → ``SeriesSettings.author_voice`` JSONB (ADR-078),
      the Delta foundation. Empty in Spec 1; filled by Spec 3 Task 2.

    Descriptive/metric boundary (ADR-055 / ADR-057 / ADR-074 — binding):
        ``render_for_generation`` renders ONLY the descriptive group
        (``voice_analysis`` descriptive fields + ``author_examples``). It MUST
        NOT read ``voice_analysis.voice_metrics`` or ``author_metrics`` — those
        metric groups are comparison-only for the future Phase 2B author-drift
        checker and never reach generation. The default Core renderer enforces
        this structurally, and :meth:`resolve_for_generation` inherits that
        guarantee by delegating to it for each block.

    Method roles:
        - :meth:`resolve_for_generation` — the GENERATION API. Produces the
          final ``{{author_voice}}`` string with the Delta composition applied
          (Spec 3 / ADR-078). This is what
          :class:`~narrare_core.writing.context_assembler.WritingContextAssembler`
          calls.
        - :meth:`get_profile` + :meth:`render_for_generation` — the LOW-LEVEL
          building blocks. Kept for non-generation consumers (e.g. the analysis
          panel, the future Phase 2B author-drift checker) that want the
          structured novel profile rather than the composed prompt string.

    Bound at Backend DI composition time. ONE implementation per Backend
    deployment. The first planned consumer is the ``WritingContextAssembler``
    (cross-feature wiring sequenced after this Core type lands).
    """

    async def get_profile(self, project_id: UUID) -> AuthorVoiceProfile | None:
        """Load the NOVEL-scoped author-voice profile.

        Low-level building block — returns the structured profile, not the
        rendered prompt string. Use :meth:`resolve_for_generation` for the
        generation path (which applies the Delta composition).

        Args:
            project_id: Project (novel) to scope the lookup.

        Returns:
            The :class:`AuthorVoiceProfile`, or ``None`` when no profile is
            stored / the JSONB is malformed (RULE-11 graceful — Pydantic
            validation on read rejects malformed payloads and the repository
            returns ``None``; never raises to the caller).
        """
        ...

    def render_for_generation(self, profile: AuthorVoiceProfile | None) -> str:
        """Render ONE profile's DESCRIPTIVE group → text (low-level).

        Renders a single profile descriptive-only (no Delta framing, no series
        context). Empty string when no profile (RULE-11). NEVER reads metrics
        (ADR-074 binding). Delegates to
        :func:`narrare_core.profiles.author_voice.render_author_voice_for_generation`.

        The generation path should call :meth:`resolve_for_generation` instead,
        which composes the Delta output via
        :func:`narrare_core.profiles.author_voice.render_author_voice_delta`.
        """
        ...

    async def resolve_for_generation(
        self,
        project_id: UUID,
        series_id: UUID | None = None,
    ) -> str:
        """Resolve the ``{{author_voice}}`` content for generation (Delta model).

        Spec 3 / ADR-078 — the Series Voice Hierarchy. Loads the novel-scoped
        and (when ``series_id`` is set) the series-scoped profile plus the
        per-novel ``use_series_voice`` opt-out flag, then delegates to the pure
        Core :func:`~narrare_core.profiles.author_voice.render_author_voice_delta`
        to compose the output:

        - series + novel voice + opt-in → ``"Series voice:\\n{series}\\n\\n
          Novel nuances:\\n{novel}"``
        - series voice only + opt-in    → ``"Series voice:\\n{series}"``
        - standalone / opt-out / no series voice / no novel voice
          → novel-only render (byte-identical to the pre-Spec-3 behaviour, or
          ``""`` when no novel profile exists — RULE-11 graceful).

        The Backend implementation owns all I/O (loading both profiles + the
        flag from their respective repositories, RULE-07) and the
        novel→series resolution. Core never touches Backend repositories; the
        resolved inputs are composed by the pure renderer.

        Args:
            project_id: The novel whose ``{{author_voice}}`` is being assembled.
            series_id: The novel's series, or ``None`` for a standalone novel.
                When ``None``, the Delta path is skipped and the output
                collapses to the legacy novel-only render (backward-compat).

        Returns:
            The fully-rendered ``{{author_voice}}`` text (Delta / series-only /
            novel-only / empty). Never raises — RULE-11 graceful degradation
            for missing / malformed data.
        """
        ...
