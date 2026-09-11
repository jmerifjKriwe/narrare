"""PreparedWikiAgent adapter tests — binds the prepare() triple halves.

Task 2 of the pydantic-ai follow-ups plan: the core ``WikiService``
drives its agent through ``WikiAgentProtocol`` (deps/stream only), while
the API factory resolves the full prepared triple via the single
assembly point. The adapter binds the settings/limits halves at
construction and forwards them into every concrete
``WikiGenerationAgent`` call (``generate_entity`` / ``generate_chapter``),
so the intent-aware settings and usage limits reach the pydantic-ai
runs without a core-layer change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pydantic_ai.usage import UsageLimits

from narrare.wiki.prepared_wiki_agent import PreparedWikiAgent
from narrare_core.wiki.types import (
    WikiChapterOutput,
    WikiEntityOutput,
    WikiGenerationDeps,
)

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings

    from narrare_core.wiki.agent import WikiGenerationAgent

_SENTINEL_SETTINGS: ModelSettings = {"max_tokens": 12_345}
_SENTINEL_LIMITS = UsageLimits(request_limit=7)


class _RecordingWikiAgent:
    """Recording fake of the concrete WikiGenerationAgent surface.

    Mirrors the Task-1 kwargs signature (deps/stream + model_settings/
    usage_limits) so the adapter's forwarded kwargs are assertable.
    """

    def __init__(self) -> None:
        self.entity_calls: list[dict[str, Any]] = []
        self.chapter_calls: list[dict[str, Any]] = []

    async def generate_entity(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
        model_settings: ModelSettings | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> WikiEntityOutput:
        self.entity_calls.append(
            {
                "deps": deps,
                "stream": stream,
                "model_settings": model_settings,
                "usage_limits": usage_limits,
            }
        )
        return WikiEntityOutput(
            narrative_summary="Entity summary.", key_attributes=[], relationships=[]
        )

    async def generate_chapter(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
        model_settings: ModelSettings | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> WikiChapterOutput:
        self.chapter_calls.append(
            {
                "deps": deps,
                "stream": stream,
                "model_settings": model_settings,
                "usage_limits": usage_limits,
            }
        )
        return WikiChapterOutput(
            narrative_summary="Chapter summary.",
            key_events=[],
            entities_involved=[],
            themes=[],
        )


def _deps() -> WikiGenerationDeps:
    return WikiGenerationDeps(
        language="en",
        genre="Fantasy",
        entity_type="character",
        entity_name="Eldrin the Wise",
        entity_body="An ancient wizard.",
    )


def _bound_agent() -> tuple[PreparedWikiAgent, _RecordingWikiAgent]:
    inner = _RecordingWikiAgent()
    # The fake mirrors the concrete agent's call surface; the cast is the
    # repo-standard fake-vs-concrete-type bridge (cf. ModelRegistry fakes).
    bound = PreparedWikiAgent(
        cast("WikiGenerationAgent", inner),
        model_settings=_SENTINEL_SETTINGS,
        usage_limits=_SENTINEL_LIMITS,
    )
    return bound, inner


class TestPreparedWikiAgent:
    """The binding adapter forwards the prepared halves into every call."""

    async def test_generate_entity_forwards_bound_halves(self) -> None:
        adapter, inner = _bound_agent()
        deps = _deps()

        result = await adapter.generate_entity(deps)

        assert result.narrative_summary == "Entity summary."
        call = inner.entity_calls[0]
        assert call["deps"] is deps
        assert call["stream"] is False
        assert call["model_settings"] is _SENTINEL_SETTINGS
        assert call["usage_limits"] is _SENTINEL_LIMITS

    async def test_generate_entity_forwards_stream_flag(self) -> None:
        adapter, inner = _bound_agent()

        await adapter.generate_entity(_deps(), stream=True)

        assert inner.entity_calls[0]["stream"] is True

    async def test_generate_chapter_forwards_bound_halves_and_stream(self) -> None:
        adapter, inner = _bound_agent()
        deps = _deps()

        result = await adapter.generate_chapter(deps, stream=True)

        assert result.narrative_summary == "Chapter summary."
        call = inner.chapter_calls[0]
        assert call["deps"] is deps
        assert call["stream"] is True
        assert call["model_settings"] is _SENTINEL_SETTINGS
        assert call["usage_limits"] is _SENTINEL_LIMITS

    async def test_none_halves_are_forwarded_explicitly(self) -> None:
        """Edge: a prepared triple without settings/limits still forwards
        explicit ``None`` kwargs — the binding contract is uniform, the
        concrete agent never silently runs with its own defaults."""
        inner = _RecordingWikiAgent()
        adapter = PreparedWikiAgent(
            cast("WikiGenerationAgent", inner), model_settings=None, usage_limits=None
        )

        await adapter.generate_entity(_deps())
        await adapter.generate_chapter(_deps())

        for call in (*inner.entity_calls, *inner.chapter_calls):
            assert call["model_settings"] is None
            assert call["usage_limits"] is None
