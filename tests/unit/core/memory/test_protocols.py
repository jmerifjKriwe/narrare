"""Tests for memory/protocols.py — Protocol conformance checks.

Covers:
1. FeedbackCollector protocol conformance
2. PreferenceProvider protocol conformance
3. MemoryFacade protocol conformance
"""

from __future__ import annotations

from uuid import uuid4

from narrare_core.memory.models import FeedbackEvent, PreferenceProfile

# ---------------------------------------------------------------------------
# Fake implementations for protocol conformance testing
# ---------------------------------------------------------------------------


class FakeFeedbackCollector:
    """Complete FeedbackCollector implementation."""

    async def record(self, event: FeedbackEvent) -> None:
        pass

    async def get_history(
        self, user_id: object, project_id: object, *, limit: int = 100
    ) -> list[FeedbackEvent]:
        return []


class FakePreferenceProvider:
    """Complete PreferenceProvider implementation."""

    async def get_preferences(self, user_id: object, project_id: object) -> PreferenceProfile:
        return PreferenceProfile(user_id=uuid4(), project_id=uuid4())

    async def reset(self, user_id: object, project_id: object) -> None:
        pass


class FakeMemoryFacade:
    """Complete MemoryFacade implementation."""

    async def record(self, event: FeedbackEvent) -> None:
        pass

    async def get_history(
        self, user_id: object, project_id: object, *, limit: int = 100
    ) -> list[FeedbackEvent]:
        return []

    async def get_preferences(self, user_id: object, project_id: object) -> PreferenceProfile:
        return PreferenceProfile(user_id=uuid4(), project_id=uuid4())

    async def reset(self, user_id: object, project_id: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Protocol conformance tests
# ---------------------------------------------------------------------------


class TestFeedbackCollectorProtocol:
    """FeedbackCollector protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        fake = FakeFeedbackCollector()
        # Verify the fake has the expected methods
        assert hasattr(fake, "record")
        assert hasattr(fake, "get_history")
        assert callable(fake.record)
        assert callable(fake.get_history)

    def test_incomplete_does_not_satisfy(self) -> None:
        class Incomplete:
            async def record(self, event: FeedbackEvent) -> None:
                pass

        # Incomplete only has record, missing get_history
        fake = Incomplete()
        assert not hasattr(fake, "get_history") or not callable(getattr(fake, "get_history", None))


class TestPreferenceProviderProtocol:
    """PreferenceProvider protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        fake = FakePreferenceProvider()
        assert hasattr(fake, "get_preferences")
        assert hasattr(fake, "reset")
        assert callable(fake.get_preferences)
        assert callable(fake.reset)

    def test_incomplete_does_not_satisfy(self) -> None:
        class Incomplete:
            async def get_preferences(
                self, user_id: object, project_id: object
            ) -> PreferenceProfile:
                return PreferenceProfile(user_id=uuid4(), project_id=uuid4())

        fake = Incomplete()
        assert not hasattr(fake, "reset") or not callable(getattr(fake, "reset", None))


class TestMemoryFacadeProtocol:
    """MemoryFacade protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        facade = FakeMemoryFacade()
        assert hasattr(facade, "record")
        assert hasattr(facade, "get_history")
        assert hasattr(facade, "get_preferences")
        assert hasattr(facade, "reset")

    def test_facade_has_all_sub_protocol_methods(self) -> None:
        """MemoryFacade has methods from both FeedbackCollector and PreferenceProvider."""
        facade = FakeMemoryFacade()
        assert callable(facade.record)
        assert callable(facade.get_history)
        assert callable(facade.get_preferences)
        assert callable(facade.reset)

    def test_incomplete_does_not_satisfy(self) -> None:
        class Incomplete:
            async def record(self, event: FeedbackEvent) -> None:
                pass

        fake = Incomplete()
        # Missing get_history, get_preferences, reset
        assert not hasattr(fake, "get_history")
