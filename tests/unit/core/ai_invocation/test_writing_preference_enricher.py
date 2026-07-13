"""Regression tests: mem0 preferences reach writing prompts end-to-end.

Investigation result (CR-AUFG-03-05):
    The PromptComposer preference gate (composer.py:93-113) DOES fire for
    writing services.  ALL writing modes put user_id/project_id into
    PromptContext.extra — see ``WritingPipeline._build_prompt_context``
    (pipeline.py:259-261) and ``pipeline_extend.py:57-59``.  The gate
    checks ``context.extra.get("user_id")`` / ``context.extra.get(
    "project_id")`` and finds them.

    ``merge_prepared_dynamic_inputs`` does NOT carry user_id/project_id
    from the ``PromptInvocationContext`` into ``PromptContext.extra`` — it
    only iterates ``dynamic_inputs``.  But it doesn't need to: writing
    modes already put them there.

    Two complementary mechanisms inject preferences:

    1. **Enricher (primary, pipeline path):** ``PreferenceContextEnricherImpl``
       reads ``PromptInvocationContext.user_id``/``project_id`` (top-level
       fields), fetches preferences, and writes
       ``dynamic_inputs["user_preferences"]``.  ``merge_prepared_dynamic_inputs``
       carries this to ``PromptContext.user_preferences`` (a dataclass
       field).  The composer gate then correctly **skips** (already set).

    2. **Gate (fallback):** If preferences aren't set by the enricher
       (provider unavailable, or pipeline not wired) and
       ``user_preferences`` is empty, the gate fires using
       ``user_id``/``project_id`` from ``extra``.

    **Conclusion:** No fix needed.  These tests prove both mechanisms work
    for writing-path invocations and that there is no double-fetch when
    both are armed with the same provider.

This module covers **mechanism 1 (enricher / pipeline path)**.  The composer
gate fallback (mechanism 2) is covered by
``test_writing_preference_composer_gate.py``.

See: CR-AUFG-03-05, ADR-038, ADR-045, CONSTRAINTS.md RULE-02/RULE-11.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest

from narrare_core.ai_invocation.enrichers.preferences import (
    PreferenceContextEnricherImpl,
)
from narrare_core.ai_invocation.models import PromptInvocationContext
from narrare_core.ai_invocation.non_writing_adapter import compose_invocation
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm.intents import LLMIntent
from narrare_core.memory.models import PreferenceProfile
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import ResolvedPrompt

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _make_profile() -> PreferenceProfile:
    """Create a PreferenceProfile with meaningful, non-empty prompt text."""
    return PreferenceProfile(
        user_id=uuid4(),
        project_id=uuid4(),
        event_count=5,
        confidence=0.8,
        style={"tone": "prefers dark, atmospheric prose"},
        content={"perspective": "favors first-person narration"},
        constraints=["avoid overly long descriptions"],
        last_updated=datetime.now(UTC),
    )


class FakePromptRegistry:
    """Minimal fake PromptRegistry returning a programmable resolved prompt."""

    def __init__(self, resolved: ResolvedPrompt | None = None) -> None:
        self._resolved = resolved or ResolvedPrompt(
            system_prompt="Write. {{user_preferences}}",
            first_message="Hello!",
            source="bundled",
            category="writing",
            language="en",
            mode="new_chapter",
            metadata={},
        )

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


class FakePreferenceProvider:
    """Async fake PreferenceProvider that tracks call count and arguments.

    A real async method avoids the ``AsyncMock(spec=...)`` pitfall where
    spec'd attributes become plain ``MagicMock`` objects that cannot be
    awaited.
    """

    def __init__(self, profile: PreferenceProfile | None = None) -> None:
        self._profile = profile or _make_profile()
        self.calls: list[tuple[object, object]] = []

    async def get_preferences(
        self,
        user_id: object,
        project_id: object,
    ) -> PreferenceProfile:
        self.calls.append((user_id, project_id))
        return self._profile

    async def reset(self, user_id: object, project_id: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Helpers — reproduce the writing-path PromptContext construction
# ---------------------------------------------------------------------------


def _writing_prompt_context(
    *,
    user_id: object,
    project_id: object,
    user_preferences: str = "",
) -> PromptContext:
    """Build a PromptContext the way writing modes do.

    Mirrors ``WritingPipeline._build_prompt_context`` (pipeline.py:259-286)
    and ``pipeline_extend.py:57-87``: user_id/project_id go into ``extra``,
    ``user_preferences`` is a dataclass field (empty unless caller sets it).
    """
    return PromptContext(
        language="en",
        project_title="Test Novel",
        mode="new_chapter",
        user_preferences=user_preferences,
        extra={
            "user_id": str(user_id),
            "project_id": str(project_id),
        },
    )


def _writing_invocation_context(
    *,
    user_id: object,
    project_id: object,
) -> PromptInvocationContext:
    """Build a PromptInvocationContext the way the writing adapter does."""
    return PromptInvocationContext(
        feature_id="writing_new_chapter",
        intent=LLMIntent.WRITE,
        user_id=user_id,
        project_id=project_id,
        language="en",
        streaming=True,
    )


# ---------------------------------------------------------------------------
# Test 1 — Pipeline-wired path: enricher injects preferences
# ---------------------------------------------------------------------------


class TestPipelineWiredPreferenceInjection:
    """When the invocation pipeline is wired with a preference enricher,
    preferences reach the merged PromptContext AND the composed prompt."""

    @pytest.mark.asyncio
    async def test_preferences_reach_merged_context_via_enricher(self) -> None:
        """Enricher fetches preferences → merge carries them to
        PromptContext.user_preferences."""
        provider = FakePreferenceProvider()
        user_id = uuid4()
        project_id = uuid4()

        pipeline = InvocationPipeline(
            enrichers=[PreferenceContextEnricherImpl(preference_provider=provider)],
        )
        composer = PromptComposer(
            cast("Any", FakePromptRegistry()),
            preference_service=cast("Any", provider),
        )

        result = await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=_writing_invocation_context(
                user_id=user_id,
                project_id=project_id,
            ),
            composer=composer,
            prompt_context=_writing_prompt_context(
                user_id=user_id,
                project_id=project_id,
            ),
            intent=LLMIntent.WRITE,
        )

        # The enricher fetched preferences and the merge carried them into
        # the merged PromptContext.user_preferences dataclass field.
        assert result.merged_context is not None
        assert result.merged_context.user_preferences != ""
        assert "dark, atmospheric prose" in result.merged_context.user_preferences

    @pytest.mark.asyncio
    async def test_preferences_reach_composed_prompt_via_enricher(self) -> None:
        """The composed prompt's system text contains the injected preferences."""
        provider = FakePreferenceProvider()
        user_id = uuid4()
        project_id = uuid4()

        pipeline = InvocationPipeline(
            enrichers=[PreferenceContextEnricherImpl(preference_provider=provider)],
        )
        composer = PromptComposer(
            cast("Any", FakePromptRegistry()),
            preference_service=cast("Any", provider),
        )

        result = await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=_writing_invocation_context(
                user_id=user_id,
                project_id=project_id,
            ),
            composer=composer,
            prompt_context=_writing_prompt_context(
                user_id=user_id,
                project_id=project_id,
            ),
            intent=LLMIntent.WRITE,
        )

        assert result.composed_prompt is not None
        assert "dark, atmospheric prose" in result.composed_prompt.system

    @pytest.mark.asyncio
    async def test_no_double_fetch_when_both_enricher_and_gate_armed(self) -> None:
        """When both the enricher and the composer gate have a provider,
        the provider is called exactly ONCE — the enricher sets
        user_preferences, so the gate's ``not context.user_preferences``
        condition is False and the gate skips."""
        provider = FakePreferenceProvider()
        user_id = uuid4()
        project_id = uuid4()

        pipeline = InvocationPipeline(
            enrichers=[PreferenceContextEnricherImpl(preference_provider=provider)],
        )
        # Composer ALSO has the same provider armed — but must NOT re-fetch.
        composer = PromptComposer(
            cast("Any", FakePromptRegistry()),
            preference_service=cast("Any", provider),
        )

        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=_writing_invocation_context(
                user_id=user_id,
                project_id=project_id,
            ),
            composer=composer,
            prompt_context=_writing_prompt_context(
                user_id=user_id,
                project_id=project_id,
            ),
            intent=LLMIntent.WRITE,
        )

        # Enricher fetched once; gate skipped (user_preferences already set).
        assert len(provider.calls) == 1
