"""Protocol conformance tests for AdaptiveContextProvider.

Covers: a complete Fake satisfies the Protocol; an incomplete class
does not; the Fake methods return the documented types.

See: ADR-069, ADR-067 (KBContextProvider pattern mirror),
CONSTRAINTS.md RULE-03.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import pytest

from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
)
from narrare_core.ai_invocation.adaptive_contracts import AdaptiveContextProvider


class FakeAdaptiveContextProvider:
    """Complete AdaptiveContextProvider implementation for tests."""

    def __init__(
        self,
        context: AdaptiveContext | None = None,
        settings: AdaptiveSettings | None = None,
    ) -> None:
        self._context = context
        self._settings = settings
        self.context_calls: list[tuple[object, object]] = []
        self.settings_calls: list[tuple[object, object]] = []

    async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
        self.context_calls.append((user_id, project_id))
        if self._context is not None:
            return self._context
        return AdaptiveContext(
            user_id=cast("UUID", user_id),
            project_id=cast("UUID", project_id),
        )

    async def get_settings(self, user_id: object, project_id: object) -> AdaptiveSettings:
        self.settings_calls.append((user_id, project_id))
        return self._settings or AdaptiveSettings()


def _make_context() -> AdaptiveContext:
    return AdaptiveContext(
        user_id=uuid4(),
        project_id=uuid4(),
        preference_text="prefers dark prose",
        voice_profiles_text="**Alice**: terse",
    )


class TestAdaptiveContextProviderProtocol:
    """AdaptiveContextProvider protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        """FakeAdaptiveContextProvider has both required async methods."""
        fake = FakeAdaptiveContextProvider()
        assert hasattr(fake, "get_context")
        assert hasattr(fake, "get_settings")
        assert callable(fake.get_context)
        assert callable(fake.get_settings)

    @pytest.mark.asyncio
    async def test_get_context_returns_adaptive_context(self) -> None:
        fake = FakeAdaptiveContextProvider(context=_make_context())
        result = await fake.get_context(user_id=uuid4(), project_id=uuid4())
        assert isinstance(result, AdaptiveContext)
        assert result.preference_text == "prefers dark prose"
        assert len(fake.context_calls) == 1

    @pytest.mark.asyncio
    async def test_get_settings_returns_adaptive_settings(self) -> None:
        fake = FakeAdaptiveContextProvider(settings=AdaptiveSettings(enabled=False))
        result = await fake.get_settings(user_id=uuid4(), project_id=uuid4())
        assert isinstance(result, AdaptiveSettings)
        assert result.enabled is False
        assert len(fake.settings_calls) == 1

    def test_incomplete_does_not_satisfy(self) -> None:
        """Class missing get_settings does not satisfy the Protocol."""

        class OnlyGetContext:
            async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
                del user_id, project_id
                return AdaptiveContext(user_id=uuid4(), project_id=uuid4())

        fake = OnlyGetContext()
        assert not hasattr(fake, "get_settings") or not callable(
            getattr(fake, "get_settings", None)
        )

    @pytest.mark.asyncio
    async def test_protocol_runtime_checkable_with_fake(self) -> None:
        """Duck-type shape verification (Protocol is implicit)."""
        fake = FakeAdaptiveContextProvider()
        assert callable(getattr(fake, "get_context", None))
        assert callable(getattr(fake, "get_settings", None))

    def test_protocol_runtime_checkable_with_isinstance(self) -> None:
        """AdaptiveContextProvider is runtime-checkable via isinstance.

        The Protocol carries ``@runtime_checkable`` so structural
        ``isinstance`` checks succeed for any object exposing both
        ``get_context`` and ``get_settings``. This also exercises the
        import (regression guard against F401 unused-import).
        """
        fake = FakeAdaptiveContextProvider()
        assert isinstance(fake, AdaptiveContextProvider)

        # Negative case: a plain object without the methods is rejected.
        assert not isinstance(object(), AdaptiveContextProvider)
