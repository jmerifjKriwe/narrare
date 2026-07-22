"""Tests for BackendProfileProvider (ADR-069 Phase 2 boundary closure).

Closes the gap noted in Phase 2: ``AdaptiveContextProviderImpl`` was wired
with ``profile_provider=None`` (no Backend impl existed). Task 15 ships the
impl. After this task, ``AdaptiveContext.voice_profiles_text`` is populated
whenever the project has at least one character KB entity with populated
``speech.voice_analysis``.

ADR-055/057 boundary: the provider surfaces ONLY the descriptive
``speech_summary`` via ``formatted_voice_profiles``. Numeric
``voice_metrics`` never enter ``AdaptiveContext``.

Note on adaptation: the plan referenced a ``KBEntityModel`` with fields
``entity_id`` / ``confidence`` / ``metadata``. The real SQLAlchemy model is
:class:`narrare.kb.models.KBEntry` (PK ``id``, metadata attr ``metadata_``,
no ``confidence`` field). These tests mock the real ``KBEntry`` shape so
they exercise the same attribute reads the production code performs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from narrare.adaptive.profile_provider_impl import BackendProfileProvider

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _as_factory(fake: Any) -> async_sessionmaker[AsyncSession]:
    """Type-narrow a plain callable to ``async_sessionmaker`` for the constructor.

    The production signature mirrors ``KBSuggestedProviderImpl`` (concrete
    ``async_sessionmaker``). Tests use plain callables returning MagicMock-based
    sessions; ``cast`` bridges the gap without weakening the production type.
    """
    return cast("async_sessionmaker[AsyncSession]", fake)


@dataclass
class _FakeEntry:
    """KBEntry-shaped value container (RULE-TEST-01: Fake over bare MagicMock).

    Mirrors :class:`narrare.kb.models.KBEntry` attribute names that
    ``BackendProfileProvider`` reads (``id``, ``metadata_``, ``name``,
    ``entity_type``, ``updated_at``). The real model stores structured
    metadata under the Python attr ``metadata_`` (mapped to the DB column
    ``metadata``); a character surfaces in the voice profile only when its
    ``speech.voice_analysis`` block is populated.
    """

    id: UUID
    entity_type: str
    name: str
    metadata_: dict[str, Any] | None
    updated_at: Any


def _character_entry(
    *,
    name: str,
    voice_analysis: dict[str, Any] | None,
    updated_at: Any = None,
) -> _FakeEntry:
    """Build a character KBEntry-shaped object with optional voice_analysis."""
    metadata: dict[str, Any] | None = None
    if voice_analysis is not None:
        metadata = {"speech": {"voice_analysis": voice_analysis}}
    return _FakeEntry(
        id=uuid4(),
        entity_type="character",
        name=name,
        metadata_=metadata,
        updated_at=updated_at,
    )


class _FakeScalarResult:
    """Mimics ``Result.scalars()`` — returns the seeded entities from ``all()``."""

    def __init__(self, entities: list[Any]) -> None:
        self._entities = entities

    def all(self) -> list[Any]:
        return self._entities


class _FakeResult:
    """Mimics the SQLAlchemy ``Result`` returned by ``session.execute()``."""

    def __init__(self, entities: list[Any]) -> None:
        self._scalar = _FakeScalarResult(entities)

    def scalars(self) -> _FakeScalarResult:
        return self._scalar


class _FakeSession:
    """Async-context-manager session mock returning seeded entities.

    ``BackendProfileProvider`` opens its session via
    ``async with self._session_factory() as session:`` (mirroring
    ``KBSuggestedProviderImpl``); this fake satisfies that protocol.
    """

    def __init__(self, entities: Iterable[Any]) -> None:
        self.execute = AsyncMock(return_value=_FakeResult(list(entities)))

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSessionFactory:
    """Callable returning the same async-CM session per call."""

    def __init__(self, entities: Iterable[Any]) -> None:
        self._session = _FakeSession(entities)

    def __call__(self) -> _FakeSession:
        return self._session


class _FailingSession:
    """Async-CM session whose ``execute`` raises (RULE-11 degradation path)."""

    def __init__(self) -> None:
        self.execute = AsyncMock(side_effect=RuntimeError("DB down"))

    async def __aenter__(self) -> _FailingSession:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FailingSessionFactory:
    """Callable returning a session whose ``execute`` raises."""

    def __call__(self) -> _FailingSession:
        return _FailingSession()


class TestGetProfileHappyPath:
    """get_profile() returns ProjectWritingProfile with voice profiles."""

    @pytest.mark.asyncio
    async def test_returns_profile_with_voice_profiles(self) -> None:
        """KB has 1 character with voice_analysis → profile populated."""
        entry = _character_entry(
            name="Alice",
            voice_analysis={
                "formality": 0.7,
                "vocabulary_level": "complex",
                "sentence_profile": "measured",
            },
        )
        factory = _FakeSessionFactory([entry])
        provider = BackendProfileProvider(session_factory=_as_factory(factory))
        profile = await provider.get_profile(project_id=uuid4())
        assert profile is not None
        # formatted_voice_profiles renders **{name}**: {speech_summary} per char
        assert "Alice" in profile.formatted_voice_profiles

    @pytest.mark.asyncio
    async def test_returns_profile_with_multiple_characters(self) -> None:
        """KB has multiple characters → all surface in the profile."""
        entries = [
            _character_entry(name="Alice", voice_analysis={"formality": 0.7}),
            _character_entry(name="Bob", voice_analysis={"formality": 0.3}),
        ]
        factory = _FakeSessionFactory(entries)
        provider = BackendProfileProvider(session_factory=_as_factory(factory))
        profile = await provider.get_profile(project_id=uuid4())
        assert profile is not None
        rendered = profile.formatted_voice_profiles
        assert "Alice" in rendered
        assert "Bob" in rendered


class TestGetProfileGracefulDegradation:
    """RULE-11: missing data returns None — never crashes."""

    @pytest.mark.asyncio
    async def test_returns_none_when_kb_empty(self) -> None:
        """No character entities → None (dashboard shows 'no voice signals')."""
        factory = _FakeSessionFactory([])
        provider = BackendProfileProvider(session_factory=_as_factory(factory))
        result = await provider.get_profile(project_id=uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_characters_have_voice_analysis(self) -> None:
        """Characters exist but none have speech.voice_analysis → None."""
        entries = [
            _character_entry(name="Alice", voice_analysis=None),
            _character_entry(name="Bob", voice_analysis=None),
        ]
        factory = _FakeSessionFactory(entries)
        provider = BackendProfileProvider(session_factory=_as_factory(factory))
        result = await provider.get_profile(project_id=uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_kb_error(self) -> None:
        """KB query raises → log warning + return None (RULE-11)."""
        provider = BackendProfileProvider(session_factory=_as_factory(_FailingSessionFactory()))
        result = await provider.get_profile(project_id=uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_project_id_unresolvable(self) -> None:
        """project_id that is not a UUID → graceful None (no DB hit)."""
        factory = _FakeSessionFactory([])
        provider = BackendProfileProvider(session_factory=_as_factory(factory))
        # An unresolvable id must short-circuit before touching the DB.
        result = await provider.get_profile(project_id="not-a-uuid")  # type: ignore[arg-type]
        assert result is None
        # The factory session was never asked to execute a query:
        assert factory._session.execute.await_count == 0


class TestVoiceMetricsBoundary:
    """ADR-055/057: voice_metrics never enter AdaptiveContext."""

    @pytest.mark.asyncio
    async def test_profile_does_not_expose_voice_metrics_text(self) -> None:
        """formatted_voice_profiles renders speech_summary, never metrics.

        The descriptive text MUST be the only voice signal surfaced.
        Numeric metrics stay on CharacterVoiceProfile.voice_metrics (which
        the adaptive enricher never reads — see adaptive_context_provider.py).
        """
        entry = _character_entry(
            name="Alice",
            voice_analysis={
                "formality": 0.7,
                "voice_metrics": {"cadence_wpm": 142, "avg_sentence_len": 11.3},
            },
        )
        factory = _FakeSessionFactory([entry])
        provider = BackendProfileProvider(session_factory=_as_factory(factory))
        profile = await provider.get_profile(project_id=uuid4())
        assert profile is not None
        text = profile.formatted_voice_profiles
        # Descriptive summary is present; numeric metrics never render here:
        assert "Alice" in text
        assert "cadence_wpm" not in text
        assert "142" not in text


class TestProtocolConformance:
    """BackendProfileProvider satisfies the Core ProfileProvider Protocol."""

    def test_satisfies_profile_provider_protocol(self) -> None:
        """ProfileProvider (ai_invocation.contracts) is not @runtime_checkable,
        so we assert structural conformance via the method signature."""
        provider = BackendProfileProvider(session_factory=_as_factory(_FakeSessionFactory([])))
        assert hasattr(provider, "get_profile")
        assert callable(provider.get_profile)
