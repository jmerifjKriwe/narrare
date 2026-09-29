"""Unit tests for ChatService KB-context wiring (ADR-067 chat follow-up).

Documented follow-up from the FO-7 chat-seam enrichment: the governed chat
template (``writing/en/chat``) carries the per-type KB placeholders
``{{kb_characters}}`` / ``{{kb_locations}}`` / ``{{kb_factions}}`` /
``{{kb_other}}`` / ``{{kb_relationships}}`` — but ``ChatService`` held no KB
dependency, so the slots rendered empty even for project-linked chat
(``build_chat_context`` documented kb_other as "wiring a provider is a
chat/dependencies.py follow-up").

This slice wires the canonical ``KBContextProviderProtocol`` (ADR-067) at
``get_chat_service`` and threads ``kb_vars`` through the chat context seam
(``_context.resolve_chat_kb_vars`` → ``build_prompt_context`` → the
``**(kb_vars or {})`` spread — never literal ``""`` keys). Degradation keeps
the FO-7 documented-empty placeholders (RULE-11): no provider wiring /
project-less chat / empty KB all compose with the baseline slots.
``kb_suggested`` stays out (AdoptionPolicy ruling pending — the enricher is
dormant repo-wide).

See:
    apps/api/narrare/chat/dependencies.py (production wiring),
    apps/api/narrare/chat/_context.py (resolve_chat_kb_vars),
    narrare_core.chat.chat_service_core.build_chat_context (empty defaults),
    tests/unit/api/chat/_kb_context_fakes.py (shared doubles),
    CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from tests.unit.api.chat._kb_context_fakes import (
    CHAT_KB_VARS_KEYS,
    KB_CHARACTERS,
    KB_FACTIONS,
    KB_LOCATIONS,
    KB_RELATIONSHIPS,
    OTHER_ENTITY_BODY,
    OTHER_ENTITY_NAME,
    FakeKbContextProvider,
    entry,
    other_entry,
    sentinel_bundle,
)

from narrare.kb.context_contracts import KBContextProviderProtocol
from narrare_core.agents.base import StreamEvent
from narrare_core.chat.chat_agent import ChatAgent
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from tests.unit.api.chat.conftest import FakeNovelLookup

    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore

# ---------------------------------------------------------------------------
# Fakes / harness — mirrors test_chat_prompt_path_compliance._make_chat_service
# ---------------------------------------------------------------------------


def _make_service(
    *,
    kb_context_provider: FakeKbContextProvider | None = None,
    novel_lookup: FakeNovelLookup | None = None,
) -> tuple[ChatService, AsyncMock]:
    """Build a ChatService with optional KB provider + novel lookup wired."""
    from tests.unit.api.chat.conftest import (
        _make_config,
        _make_mock_registry,
        _static_resolution,
    )

    from narrare.chat.chat_service import ChatService
    from narrare_core.chat.conversation_store import InMemoryConversationStore

    composer = AsyncMock(name="kb_context_composer")
    composer.build = AsyncMock(return_value=ComposedPrompt(system="S", user="U"))
    service = ChatService(
        prompt_composer=composer,
        model_registry=_make_mock_registry(),
        conversation_store=cast(
            "SQLAlchemyConversationStore",
            InMemoryConversationStore(),
        ),
        model_resolution=_static_resolution(_make_config()),
        kb_context_provider=kb_context_provider,
        novel_lookup=novel_lookup,
    )
    return service, composer


def _recording_agent() -> MagicMock:
    """ChatAgent stand-in streaming one done event (RULE-TEST-01 spec'd)."""

    async def _events() -> AsyncIterator[StreamEvent]:
        yield StreamEvent(type="done", text="ok", usage={}, new_messages=[])

    mock_agent = MagicMock(name="kb_context_agent", spec=ChatAgent)
    mock_agent.run_stream.side_effect = lambda *a, **kw: _events()
    return mock_agent


async def _capture_prompt_context(
    service: ChatService,
    composer: AsyncMock,
    user_id: UUID,
    *,
    project_id: UUID | None,
) -> PromptContext:
    """Drive ``ask()`` and return the PromptContext passed to ``composer.build``."""
    from narrare_core.chat.contracts import ChatRequest

    request = ChatRequest(project_id=project_id, message="Craft question")
    with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=_recording_agent()):
        async for _ in await service.ask(request, user_id):
            pass

    call = composer.build.await_args
    assert call is not None, "composer.build was never awaited"
    context = call.args[1]
    assert isinstance(context, PromptContext)
    return context


def _seeded_novel_lookup() -> tuple[FakeNovelLookup, UUID, UUID]:
    """A ``FakeNovelLookup`` with one owned novel — ``(lookup, novel, owner)``."""
    from tests.unit.api.chat.conftest import FakeNovelLookup

    novel_id, owner_id = uuid4(), uuid4()
    lookup = FakeNovelLookup()
    lookup.seed_owned(
        novel_id,
        owner_id,
        title="SENTINEL_NOVEL_TITLE_c1ad",
        genre="SENTINEL_NOVEL_GENRE_d2be",
    )
    return lookup, novel_id, owner_id


def _populated_provider() -> FakeKbContextProvider:
    """A provider with sentinel bundle slots + one non-slot ``kb_other`` entry."""
    return FakeKbContextProvider(
        bundle=sentinel_bundle(),
        entries=[other_entry()],
    )


# ---------------------------------------------------------------------------
# resolve_chat_kb_vars — the seam resolver (unit level)
# ---------------------------------------------------------------------------


class TestResolveChatKbVars:
    """``_context.resolve_chat_kb_vars`` — per-type KB vars from ADR-067."""

    async def test_populated_provider_returns_per_type_sentinels(self) -> None:
        """Every bundle slot + the kb_other catch-all carry real renders."""
        from narrare.chat._context import resolve_chat_kb_vars

        kb_vars = await resolve_chat_kb_vars(
            kb_context_provider=_populated_provider(),
            novel_id=uuid4(),
        )

        assert kb_vars is not None
        assert kb_vars["kb_characters"] == KB_CHARACTERS
        assert kb_vars["kb_locations"] == KB_LOCATIONS
        assert kb_vars["kb_factions"] == KB_FACTIONS
        assert kb_vars["kb_relationships"] == KB_RELATIONSHIPS
        # kb_other flows through the real format_entities renderer.
        assert OTHER_ENTITY_NAME in kb_vars["kb_other"]
        assert OTHER_ENTITY_BODY in kb_vars["kb_other"]

    async def test_slot_entity_types_do_not_leak_into_kb_other(self) -> None:
        """character/location/faction entries stay in their bundle slots."""
        from narrare.chat._context import resolve_chat_kb_vars

        provider = FakeKbContextProvider(
            bundle=sentinel_bundle(),
            entries=[
                entry("character", "Elara"),
                entry("location", "Keep"),
                entry("faction", "Watch"),
            ],
        )

        kb_vars = await resolve_chat_kb_vars(
            kb_context_provider=provider,
            novel_id=uuid4(),
        )

        assert kb_vars is not None
        assert kb_vars["kb_other"] == ""

    async def test_empty_kb_degrades_to_empty_slot_values(self) -> None:
        """An empty KB (degradation bundle, no entries) yields all-"" vars."""
        from narrare.chat._context import resolve_chat_kb_vars

        kb_vars = await resolve_chat_kb_vars(
            kb_context_provider=FakeKbContextProvider(),
            novel_id=uuid4(),
        )

        assert kb_vars is not None
        assert set(kb_vars) == CHAT_KB_VARS_KEYS
        assert all(value == "" for value in kb_vars.values())

    async def test_kb_other_inherits_formatter_count_cap(self) -> None:
        """kb_other renders through the capped formatter: >cap → marker.

        The seam passes no override, so the formatter default applies —
        chat's kb_other catch-all is no longer uncapped (budget follow-up).
        """
        from narrare.chat._context import resolve_chat_kb_vars

        provider = FakeKbContextProvider(
            bundle=sentinel_bundle(),
            entries=[entry("system", f"System {i:03d}", f"Body {i:03d}.") for i in range(55)],
        )

        kb_vars = await resolve_chat_kb_vars(
            kb_context_provider=provider,
            novel_id=uuid4(),
        )

        assert kb_vars is not None
        assert "[… 5 more entities omitted]" in kb_vars["kb_other"]
        assert "System 049" in kb_vars["kb_other"]
        assert "System 050" not in kb_vars["kb_other"]

    async def test_no_provider_returns_none(self) -> None:
        """Unwired provider (test contexts) → ``None`` → or-{} no-op spread."""
        from narrare.chat._context import resolve_chat_kb_vars

        assert await resolve_chat_kb_vars(kb_context_provider=None, novel_id=uuid4()) is None

    async def test_projectless_returns_none_without_provider_calls(self) -> None:
        """Project-less chat performs no KB fetches (NOTES-001 §6b)."""
        from narrare.chat._context import resolve_chat_kb_vars

        provider = FakeKbContextProvider()

        kb_vars = await resolve_chat_kb_vars(
            kb_context_provider=provider,
            novel_id=None,
        )

        assert kb_vars is None
        assert provider.fetch_context_calls == []
        assert provider.fetch_entities_calls == []

    def test_fake_satisfies_provider_protocol(self) -> None:
        """RULE-03 pin: the fake structurally satisfies the ADR-067 Protocol."""
        assert isinstance(FakeKbContextProvider(), KBContextProviderProtocol)


# ---------------------------------------------------------------------------
# ChatService.ask — threading through the production seam
# ---------------------------------------------------------------------------


class TestAskKbContextEnrichment:
    """``ask()`` threads ``kb_vars`` into the composed prompt context."""

    async def test_ask_with_provider_threads_kb_vars_into_context(self) -> None:
        """Project-linked chat carries the per-type renders in ``extra``."""
        novel_lookup, novel_id, owner_id = _seeded_novel_lookup()
        service, composer = _make_service(
            kb_context_provider=_populated_provider(),
            novel_lookup=novel_lookup,
        )

        context = await _capture_prompt_context(
            service,
            composer,
            owner_id,
            project_id=novel_id,
        )

        assert context.extra["kb_characters"] == KB_CHARACTERS
        assert context.extra["kb_locations"] == KB_LOCATIONS
        assert context.extra["kb_factions"] == KB_FACTIONS
        assert context.extra["kb_relationships"] == KB_RELATIONSHIPS
        assert OTHER_ENTITY_NAME in context.extra["kb_other"]

    async def test_ask_projectless_keeps_baseline_without_kb_calls(self) -> None:
        """Project-less chat: baseline slots, zero KB fetches (NOTES-001)."""
        provider = FakeKbContextProvider(bundle=sentinel_bundle())
        service, composer = _make_service(kb_context_provider=provider)

        context = await _capture_prompt_context(
            service,
            composer,
            uuid4(),
            project_id=None,
        )

        assert provider.fetch_context_calls == []
        assert provider.fetch_entities_calls == []
        assert context.extra["kb_characters"] == ""
        assert context.extra["kb_other"] == ""

    async def test_ask_without_provider_wiring_keeps_documented_empty_slots(
        self,
    ) -> None:
        """Unwired provider (test contexts): FO-7 slots stay documented-empty."""
        novel_lookup, novel_id, owner_id = _seeded_novel_lookup()
        service, composer = _make_service(novel_lookup=novel_lookup)

        context = await _capture_prompt_context(
            service,
            composer,
            owner_id,
            project_id=novel_id,
        )

        assert context.extra["kb_characters"] == ""
        assert context.extra["kb_locations"] == ""
        assert context.extra["kb_factions"] == ""
        assert context.extra["kb_relationships"] == ""
        assert context.extra["kb_other"] == ""


# ---------------------------------------------------------------------------
# Real-composer compose — the seam-supplied vars render (RULE-22)
# ---------------------------------------------------------------------------


class TestChatKbVarsCompose:
    """Real Registry+Composer: populated kb_vars render, baseline unchanged."""

    async def test_populated_kb_vars_render_into_composed_system(self) -> None:
        """The seam-built context composes with the sentinels — no residue."""
        from narrare.chat._context import build_prompt_context, resolve_chat_kb_vars

        kb_vars = await resolve_chat_kb_vars(
            kb_context_provider=_populated_provider(),
            novel_id=uuid4(),
        )
        context = build_prompt_context([], kb_vars=kb_vars)

        prompt = await PromptComposer(PromptRegistry()).build(
            LLMIntent.CHAT, context, user_prompt="Craft question"
        )

        assert KB_CHARACTERS in prompt.system
        assert KB_LOCATIONS in prompt.system
        assert KB_FACTIONS in prompt.system
        assert KB_RELATIONSHIPS in prompt.system
        assert OTHER_ENTITY_NAME in prompt.system
        assert "{{" not in prompt.system, "placeholder residue in render"

    async def test_empty_kb_vars_baseline_composes_unchanged(self) -> None:
        """kb_vars=None (or-{} no-op) composes exactly like the pre-slice tier."""
        from narrare.chat._context import build_prompt_context

        context = build_prompt_context([], kb_vars=None)

        prompt = await PromptComposer(PromptRegistry()).build(
            LLMIntent.CHAT, context, user_prompt="Craft question"
        )

        for sentinel in (KB_CHARACTERS, KB_LOCATIONS, KB_FACTIONS):
            assert sentinel not in prompt.system
        assert "{{" not in prompt.system, "placeholder residue in render"


__all__ = [
    "FakeKbContextProvider",
    "TestAskKbContextEnrichment",
    "TestChatKbVarsCompose",
    "TestResolveChatKbVars",
]
