"""Tests for preference auto-injection in PromptComposer.build().

Verifies that:
- Preferences are auto-resolved when the service is configured and context is empty
- Existing preferences in context are not overridden
- Build proceeds normally when no service is configured (backward compatible)
- Build proceeds without preferences when the service raises an exception
- No resolution is attempted when context.extra lacks user_id/project_id
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from narrare_core.llm import LLMIntent
from narrare_core.memory.models import PreferenceProfile
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import ResolvedPrompt


def _make_resolved(system: str = "System.", first: str | None = "Hello!") -> ResolvedPrompt:
    return ResolvedPrompt(
        system_prompt=system,
        first_message=first,
        source="bundled",
        category="writing",
        language="en",
        mode="new_chapter",
        metadata={},
    )


class FakePromptRegistry:
    """Minimal fake for PromptRegistry — returns programmable resolved prompts."""

    def __init__(self, resolved: ResolvedPrompt | None = None) -> None:
        self._resolved = resolved or _make_resolved()

    async def resolve(
        self,
        *,
        category: str,
        language: str,
        mode: str,
        genre: str | None = None,
        db_content: str | None = None,
    ) -> ResolvedPrompt:
        return self._resolved

    async def resolve_name_style(
        self,
        *,
        category: str,
        language: str,
        style_id: str,
    ) -> str:
        return ""


class FakePreferenceService:
    """Fake PreferenceProvider that returns a programmable profile."""

    def __init__(self, profile: PreferenceProfile | None = None) -> None:
        self._profile = profile
        self.call_count: int = 0
        self.last_user_id: Any = None
        self.last_project_id: Any = None

    async def get_preferences(
        self,
        user_id: Any,
        project_id: Any,
    ) -> PreferenceProfile:
        self.call_count += 1
        self.last_user_id = user_id
        self.last_project_id = project_id
        if self._profile is None:
            return PreferenceProfile(
                user_id=user_id if hasattr(user_id, "hex") else uuid4(),
                project_id=project_id if hasattr(project_id, "hex") else uuid4(),
            )
        return self._profile

    def reset(self, user_id: Any, project_id: Any) -> None:
        pass


class FailingPreferenceService:
    """PreferenceProvider that always raises an exception."""

    async def get_preferences(self, user_id: Any, project_id: Any) -> PreferenceProfile:
        raise RuntimeError("mem0 unavailable")

    def reset(self, user_id: Any, project_id: Any) -> None:
        pass


def _profile_with_preferences() -> PreferenceProfile:
    """Create a PreferenceProfile with meaningful preferences."""
    return PreferenceProfile(
        user_id=uuid4(),
        project_id=uuid4(),
        event_count=5,
        confidence=0.25,
        style={"tone": "prefers dark, atmospheric prose"},
        content={"perspective": "favors first-person narration"},
        constraints=["avoid overly long descriptions"],
    )


class TestPreferenceAutoInjection:
    """Task 7.5: Preference auto-injection tests."""

    async def test_preferences_auto_populated_when_service_configured(self) -> None:
        """When PreferenceService configured and context.user_preferences empty and
        user_id/project_id in extra: preferences auto-populated."""
        profile = _profile_with_preferences()
        pref_service = FakePreferenceService(profile)
        registry = FakePromptRegistry(
            _make_resolved(system="Write for {{project_title}}. {{user_preferences}}")
        )
        composer = PromptComposer(registry, preference_service=pref_service)  # type: ignore[arg-type]

        user_id = uuid4()
        project_id = uuid4()
        ctx = PromptContext(
            language="en",
            project_title="Test Novel",
            extra={"user_id": str(user_id), "project_id": str(project_id)},
        )
        result = await composer.build(LLMIntent.WRITE, ctx)

        # The preference service was called
        assert pref_service.call_count == 1
        # The system prompt contains the injected preference text
        assert "Style preferences" in result.system
        assert "prefers dark, atmospheric prose" in result.system

    async def test_existing_preferences_not_overridden(self) -> None:
        """When PreferenceService configured but context.user_preferences already set:
        no override."""
        profile = _profile_with_preferences()
        pref_service = FakePreferenceService(profile)
        registry = FakePromptRegistry(_make_resolved(system="Write. {{user_preferences}}"))
        composer = PromptComposer(registry, preference_service=pref_service)  # type: ignore[arg-type]

        ctx = PromptContext(
            language="en",
            user_preferences="Custom pre-set preferences.",
            extra={"user_id": str(uuid4()), "project_id": str(uuid4())},
        )
        result = await composer.build(LLMIntent.WRITE, ctx)

        # The preference service was NOT called
        assert pref_service.call_count == 0
        # The system prompt uses the existing preferences
        assert "Custom pre-set preferences." in result.system
        assert "Style preferences" not in result.system

    async def test_no_service_backward_compatible(self) -> None:
        """When no PreferenceService configured: build proceeds normally."""
        registry = FakePromptRegistry()
        composer = PromptComposer(registry)  # type: ignore[arg-type]

        ctx = PromptContext(
            language="en",
            extra={"user_id": str(uuid4()), "project_id": str(uuid4())},
        )
        result = await composer.build(LLMIntent.WRITE, ctx)

        # Build succeeds without error
        assert result.system == "System."
        assert result.user == "Hello!"

    async def test_service_exception_build_proceeds(self) -> None:
        """When PreferenceService raises exception: build proceeds without preferences
        (warning logged)."""
        pref_service = FailingPreferenceService()
        registry = FakePromptRegistry(_make_resolved(system="Write. {{user_preferences}}"))
        composer = PromptComposer(registry, preference_service=pref_service)  # type: ignore[arg-type]

        ctx = PromptContext(
            language="en",
            extra={"user_id": str(uuid4()), "project_id": str(uuid4())},
        )
        result = await composer.build(LLMIntent.WRITE, ctx)

        # Build succeeds — user_preferences replaced with empty string (strict=False
        # substitutes the empty value from context.user_preferences default)
        assert "Style preferences" not in result.system
        assert "{{user_preferences}}" not in result.system

    async def test_no_resolution_without_user_and_project_ids(self) -> None:
        """When context.extra has no user_id/project_id: no preference resolution
        attempted."""
        profile = _profile_with_preferences()
        pref_service = FakePreferenceService(profile)
        registry = FakePromptRegistry()
        composer = PromptComposer(registry, preference_service=pref_service)  # type: ignore[arg-type]

        # No user_id or project_id
        ctx = PromptContext(language="en", extra={})
        _result = await composer.build(LLMIntent.WRITE, ctx)

        assert pref_service.call_count == 0

    async def test_no_resolution_with_only_user_id(self) -> None:
        """When context.extra has only user_id but no project_id: no resolution."""
        profile = _profile_with_preferences()
        pref_service = FakePreferenceService(profile)
        registry = FakePromptRegistry()
        composer = PromptComposer(registry, preference_service=pref_service)  # type: ignore[arg-type]

        ctx = PromptContext(language="en", extra={"user_id": str(uuid4())})
        _result = await composer.build(LLMIntent.WRITE, ctx)

        assert pref_service.call_count == 0

    async def test_empty_profile_does_not_update_context(self) -> None:
        """When PreferenceService returns an empty profile (event_count=0):
        preferences not injected because to_prompt_text() returns ''."""
        empty_profile = PreferenceProfile(
            user_id=uuid4(),
            project_id=uuid4(),
            event_count=0,
        )
        pref_service = FakePreferenceService(empty_profile)
        registry = FakePromptRegistry(_make_resolved(system="Write. {{user_preferences}}"))
        composer = PromptComposer(registry, preference_service=pref_service)  # type: ignore[arg-type]

        ctx = PromptContext(
            language="en",
            extra={"user_id": str(uuid4()), "project_id": str(uuid4())},
        )
        result = await composer.build(LLMIntent.WRITE, ctx)

        # Service was called but profile was empty → user_preferences stays "" in context
        # substitute() replaces {{user_preferences}} with the empty string value
        assert pref_service.call_count == 1
        assert "Style preferences" not in result.system
        assert "{{user_preferences}}" not in result.system
