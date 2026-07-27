"""Profile contracts — Protocols for profile assembly dependencies.

RULE-03: Contract before implementation.

This module defines the **Voice Profile SSOT contracts** (ADR-040 §1
plus ADR-050 P1-C extension). Two contracts cooperate:

* :class:`VoiceProfileProvider` — the **producer** side: loads voice
  profiles from KB (or any future storage). Implemented once in
  Backend; injected wherever voice data is needed.
* :class:`VoiceProfileConsumer` — the **consumer** side: every code
  path that uses voice profiles in a prompt or in a consistency
  check MUST go through a registered consumer bound to a single
  provider instance per invocation. This closes the ADR-040 Layer 4
  gap where ``WritingContextAssembler.assemble()`` still calls
  ``extract_voice_profiles()`` directly (bypassing the SSOT) while
  ``ProfileAssembler`` consumes the provider.

Why two contracts and not one: generation and checking have
different call shapes (generation wants formatted text for the
prompt; checking wants structured data for rule evaluation). They
share the same source of truth and freshness signal but differ in
projection. Splitting producer from consumer lets each consumer
project as needed without recreating the provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.profiles.author_voice import AuthorVoiceProfile
    from narrare_core.profiles.models import CharacterVoiceProfile, ProjectWritingProfile


@runtime_checkable
class VoiceProfileProvider(Protocol):
    """Provides character voice data for profile assembly.

    Producer-side contract: ONE implementation per Backend deployment,
    injected via DI. The implementation reads from KB entities
    (``KBEntry.metadata_["speech"]`` / ``["personality"]``) and applies
    freshness rules (``profiles/_freshness.py``). It MUST return the
    same result set for the same ``(project_id, max_age_days)`` within
    a single invocation so that generation and checking see identical
    voice data.

    Freshness contract: every returned :class:`CharacterVoiceProfile`
    MUST have ``is_fresh`` and ``updated_at`` populated. Consumers
    MUST NOT silently drop stale profiles — they project them with a
    warning marker (generation) or include them with reduced
    confidence (checking).
    """

    async def get_character_voices(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        """Load character voice profiles for a project.

        Args:
            project_id: Project to scope the lookup.
            max_age_days: Maximum age in days for a profile to be
                considered fresh. Default 30. Implementations MUST
                honour this argument so callers can request a stricter
                freshness window for checking use-cases.

        Returns:
            List of :class:`CharacterVoiceProfile` with ``is_fresh``
            populated. May be empty when no character entities exist
            with voice metadata. Ordering is implementation-defined
            but MUST be stable across calls within one invocation.
        """
        ...


@runtime_checkable
class VoiceProfileConsumer(Protocol):
    """Consumer-side contract for voice profile data.

    Every code path that uses voice profile data in a prompt
    (generation, e.g. ``WritingContextAssembler``,
    ``WritingPipeline`` sub-pipelines) or in a consistency check
    (CONS-001, WRITE-010 voice checker) MUST be wired to a single
    :class:`VoiceProfileConsumer` per invocation, and that consumer
    MUST be bound to a single :class:`VoiceProfileProvider`.

    Why this contract exists (ADR-050 P1-C — CR-AUFG-04-09):

    * Before ADR-040 Layer 4 wiring, ``WritingContextAssembler``
      called ``extract_voice_profiles(entities)`` directly — a
      free function in ``writing/_voice_profiles.py`` (backward-compat
      shim over ``profiles/_voice_extraction.py``). This bypassed the
      provider/SSOT and meant freshness policy lived at the call site,
      not at the provider.
    * Future checking paths (WRITE-010 Voice Consistency Checker,
      ANAL-008 Character Voice Profiling) would naturally duplicate
      the freshness logic if not bound to the same provider.
    * ADR-040 §1 Decision A requires KB voice extraction to be a
      "strategy behind the profile contract, not the caller's
      responsibility." That decision is half-implemented (Layer 1 in
      Core is done; Layer 4 wiring is not). This Protocol is the
      contract that makes Layer 4 enforceable.

    Consumer implementations are bound at Backend DI composition time.
    A single ``ProfileAssembler`` instance typically serves both
    generation and checking for one request scope.
    """

    @property
    def provider(self) -> VoiceProfileProvider:
        """The bound provider. MUST be the same instance for every
        consumer in a single invocation so generation and checking
        observe identical voice data."""
        ...

    async def assemble_for_generation(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> ProjectWritingProfile:
        """Project the bound provider's data into a generation-ready
        :class:`ProjectWritingProfile`.

        The returned profile MUST carry freshness warnings for every
        stale voice profile (no silent degradation, RULE-11).
        Implementations typically delegate to
        :class:`profiles.assembly.ProfileAssembler` after fetching
        voices from ``self.provider``.
        """
        ...

    async def assemble_for_checking(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        """Project the bound provider's data into structured profiles
        for consistency checking.

        Returns the raw structured profiles (not formatted text) so
        consumers like WRITE-010 can apply their own rule logic.
        Stale profiles MUST be included with ``is_fresh=False`` —
        checking needs to see them to flag drift, not silently drop
        them.
        """
        ...


@runtime_checkable
class AuthorVoiceConsumer(Protocol):
    """Consumer-side contract for author-voice data (ADR-074 / ANAL-007).

    Parallel to :class:`VoiceProfileConsumer`, but for the AUTHOR voice (the
    narrator's prose voice, novel-scoped). Reads ``ProjectSettings.author_voice``
    JSONB via the Backend ``AuthorVoiceRepository`` and renders the DESCRIPTIVE
    group into ``{{author_voice}}``.

    Descriptive/metric boundary (ADR-055 / ADR-057 / ADR-074 — binding):
        ``render_for_generation`` renders ONLY the descriptive group
        (``voice_analysis`` descriptive fields + ``author_examples``). It MUST
        NOT read ``voice_analysis.voice_metrics`` or ``author_metrics`` — those
        metric groups are comparison-only for the future Phase 2B author-drift
        checker and never reach generation. The default Core renderer enforces
        this structurally.

    Bound at Backend DI composition time. ONE implementation per Backend
    deployment. The first planned consumer is the ``WritingContextAssembler``
    (cross-feature wiring sequenced after this Core type lands).
    """

    async def get_profile(self, project_id: UUID) -> AuthorVoiceProfile | None:
        """Load the author-voice profile for a project.

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
        """Render the DESCRIPTIVE group → ``{{author_voice}}`` text.

        Empty string when no profile (RULE-11). NEVER reads metrics
        (ADR-074 binding). Delegates to
        :func:`narrare_core.profiles.author_voice.render_author_voice_for_generation`.
        """
        ...
