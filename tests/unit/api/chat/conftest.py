"""Shared fixtures and helpers for ChatService unit tests."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from uuid import UUID

    from pydantic_ai.usage import UsageLimits

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare.notes.contracts import OwnedLinkLookupProtocol
    from narrare_core.agents.base import StreamEvent
    from narrare_core.chat.contracts import ChatMessage
    from narrare_core.chat.conversation_store import InMemoryConversationStore
    from narrare_core.llm import ResolvedModelConfig

from narrare_core.chat.contracts import ChatRequest
from narrare_core.shared.errors import NotFoundError

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


async def _async_gen(*events: StreamEvent) -> AsyncIterator[StreamEvent]:
    """Turn StreamEvent instances into an async generator.

    Use this to simulate ``ChatAgent.run_stream()`` return values in tests.
    """
    for event in events:
        yield event


class FakeChatService:
    """In-memory Fake for ChatServiceProtocol (ADR-030).

    Allows configuring stream events, history, project_id, and the
    conversation owner per test. Records clear_history calls for
    verification.

    Ownership semantics mirror the real service contract: when an owner is
    configured via ``set_owner()``, history access by any other user raises
    ``NotFoundError`` (mapped to HTTP 404 by the global NarrareError
    handler — foreign and unknown conversations are indistinguishable).
    """

    def __init__(self) -> None:
        self._events: list[dict[str, object]] = []
        self._history: list[ChatMessage] = []
        self._project_id: UUID | None = None
        self._owner_id: UUID | None = None
        self._ask_error: Exception | None = None
        self.cleared_ids: list[UUID] = []

    def set_stream_events(self, *events: dict[str, object]) -> None:
        """Pre-configure the events that ``ask()`` will stream."""
        self._events = list(events)

    def set_history(self, *messages: ChatMessage) -> None:
        """Pre-configure messages returned by ``get_history()``."""
        self._history = list(messages)

    def set_project_id(self, project_id: UUID | None) -> None:
        """Set the project_id returned by ``get_project_id_for_conversation()``."""
        self._project_id = project_id

    def set_owner(self, owner_id: UUID) -> None:
        """Set the user that owns the configured conversation.

        While set, history access by any other user_id raises NotFoundError.
        """
        self._owner_id = owner_id

    def set_ask_error(self, error: Exception) -> None:
        """Make ``ask()`` raise — e.g. NotFoundError for foreign conversations."""
        self._ask_error = error

    def _require_owner(self, conversation_id: UUID, user_id: UUID) -> None:
        """Raise NotFoundError when another user accesses the conversation."""
        if self._owner_id is not None and user_id != self._owner_id:
            raise NotFoundError("ChatConversation", identifier=str(conversation_id))

    async def ask(
        self,
        request: ChatRequest,
        user_id: UUID,
    ) -> AsyncIterator[dict[str, object]]:
        """Return a pre-configured async stream of events (or raise)."""
        if self._ask_error is not None:
            raise self._ask_error

        async def _stream() -> AsyncIterator[dict[str, object]]:
            for event in self._events:
                yield event

        return _stream()

    async def get_history(
        self,
        conversation_id: UUID,
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        self._require_owner(conversation_id, user_id)
        return list(self._history)

    async def get_project_id_for_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> UUID | None:
        self._require_owner(conversation_id, user_id)
        return self._project_id

    async def clear_history(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> None:
        self._require_owner(conversation_id, user_id)
        self.cleared_ids.append(conversation_id)


def _make_mock_composer() -> AsyncMock:
    """Create a mock PromptComposer that returns a known ComposedPrompt."""
    from narrare_core.prompts.composer import ComposedPrompt

    composer = AsyncMock()
    composer.build = AsyncMock(
        return_value=ComposedPrompt(
            system="You are a helpful writing assistant.",
            user="Hello!",
        )
    )
    return composer


def _make_mock_registry() -> AsyncMock:
    """Create a mock ModelRegistry.

    Task 6d-1: the service resolves via ``prepare()`` (single assembly
    point). The bridge delegates to ``get_model`` so tests keep configuring
    ``registry.get_model.return_value`` — the resolved model reaches the
    agent unchanged, with no settings/limits layered on (pre-6d behavior).
    """
    from narrare_core.llm._prepared_call import PreparedModelCall

    registry = AsyncMock()
    registry.get_model = AsyncMock()

    async def _prepare(
        config: object,
        *,
        intent: object = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        _ = intent
        return PreparedModelCall(
            model=await registry.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )

    registry.prepare = AsyncMock(side_effect=_prepare)
    return registry


def _make_config() -> MagicMock:
    """Create a mock ResolvedModelConfig."""
    from narrare_core.llm import ResolvedModelConfig

    config = MagicMock(spec=ResolvedModelConfig)
    config.provider_name = "anthropic"
    config.model_id = "claude-sonnet-4-5-20251020"
    return config


def _static_resolution(config: object) -> ModelResolution:
    """``StaticModelResolution`` over a fixed config (ADR-086 L12 seam).

    The eager factory passed ``config``/``api_key``/``base_url`` into the
    service; since ADR-086 L12 the service takes a ``ModelResolution`` —
    unit tests migrate mechanically to ``StaticModelResolution`` with a
    fixed triple (outcomes unchanged).
    """
    from narrare._app.dependencies_services import StaticModelResolution
    from narrare_core.llm.model_routing import ResolvedModel

    return StaticModelResolution(
        ResolvedModel(
            config=cast("ResolvedModelConfig", config),
            api_key="sk-test-key",
            base_url=None,
        )
    )


def _make_request(
    message: str = "Hello!",
    conversation_id: UUID | None = None,
) -> ChatRequest:
    """Create a ChatRequest with sensible defaults."""
    from uuid import uuid4

    return ChatRequest(
        project_id=uuid4(),
        message=message,
        conversation_id=conversation_id,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _OwnedNovel:
    """Novel-shaped stand-in returned by ``FakeNovelLookup``.

    Carries the metadata fields the chat seam reads (``title`` / ``genre``)
    so context-enrichment tests can assert on sentinel values. Unseeded
    ids still resolve to a bare ``object()`` (non-novel shape) so the
    metadata degradation path stays exercisable.
    """

    def __init__(self, title: str, genre: str) -> None:
        self.title = title
        self.genre = genre


class FakeNovelLookup:
    """In-memory Fake for OwnedLinkLookupProtocol (ADR-030).

    Returns the novel only for its seeded (novel_id, owner_id) pair —
    foreign or unknown ids resolve to ``None`` (the service then raises
    NotFoundError, notes ``_validate_link`` semantics).
    """

    def __init__(self) -> None:
        self._owned: dict[UUID, UUID] = {}
        self._novels: dict[UUID, _OwnedNovel] = {}
        self.calls: list[tuple[UUID, UUID]] = []

    def seed_owned(
        self,
        novel_id: UUID,
        owner_id: UUID,
        *,
        title: str = "",
        genre: str = "",
    ) -> None:
        """Register a novel as owned by ``owner_id`` (with seam metadata)."""
        self._owned[novel_id] = owner_id
        self._novels[novel_id] = _OwnedNovel(title=title, genre=genre)

    async def get_owned(self, entity_id: UUID, user_id: UUID) -> object | None:
        self.calls.append((entity_id, user_id))
        if self._owned.get(entity_id) == user_id:
            return self._novels.get(entity_id, object())
        return None


@pytest.fixture
def mock_composer() -> AsyncMock:
    return _make_mock_composer()


@pytest.fixture
def mock_registry() -> AsyncMock:
    return _make_mock_registry()


@pytest.fixture
def mock_config() -> MagicMock:
    return _make_config()


@pytest.fixture
def in_memory_store() -> InMemoryConversationStore:
    """InMemoryConversationStore — no DB needed for unit tests."""
    from narrare_core.chat.conversation_store import InMemoryConversationStore

    return InMemoryConversationStore()


@pytest.fixture
def service(
    mock_composer: AsyncMock,
    mock_registry: AsyncMock,
    in_memory_store: InMemoryConversationStore,
    mock_config: MagicMock,
) -> ChatService:
    """Create a ``ChatService`` with fully mocked dependencies."""
    from narrare.chat.chat_service import ChatService

    return ChatService(
        prompt_composer=mock_composer,
        model_registry=mock_registry,
        conversation_store=cast("SQLAlchemyConversationStore", in_memory_store),
        model_resolution=_static_resolution(mock_config),
    )


@pytest.fixture
def novel_lookup() -> FakeNovelLookup:
    """Ownership-scoped novel lookup Fake (OwnedLinkLookupProtocol)."""
    return FakeNovelLookup()


@pytest.fixture
def service_with_novel_lookup(
    mock_composer: AsyncMock,
    mock_registry: AsyncMock,
    in_memory_store: InMemoryConversationStore,
    mock_config: MagicMock,
    novel_lookup: FakeNovelLookup,
) -> ChatService:
    """ChatService with the novel-ownership lookup wired (production shape)."""
    from narrare.chat.chat_service import ChatService

    return ChatService(
        prompt_composer=mock_composer,
        model_registry=mock_registry,
        conversation_store=cast("SQLAlchemyConversationStore", in_memory_store),
        model_resolution=_static_resolution(mock_config),
        novel_lookup=cast("OwnedLinkLookupProtocol", novel_lookup),
    )


# ---------------------------------------------------------------------------
# ADR-089 dynamic tiering pilot — CoreSettings flag control (ADR-071 §8)
# ---------------------------------------------------------------------------


@pytest.fixture
def tiering_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Enable the ADR-089 pilot flag (ADR-071 §8 env + cache-clear pattern)."""
    from narrare_core.settings import get_core_settings

    monkeypatch.setenv("NARRARE_LLM_DYNAMIC_TIERING", "true")
    get_core_settings.cache_clear()
    yield
    get_core_settings.cache_clear()


@pytest.fixture
def tiering_off(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pin the pilot flag OFF (the shipped default) regardless of env."""
    from narrare_core.settings import get_core_settings

    monkeypatch.delenv("NARRARE_LLM_DYNAMIC_TIERING", raising=False)
    get_core_settings.cache_clear()
    yield
    get_core_settings.cache_clear()
