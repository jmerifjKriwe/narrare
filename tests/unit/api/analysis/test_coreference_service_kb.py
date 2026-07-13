"""KB-context population tests for CoreferenceService (ANAL-005).

Verifies that ``CoreferenceService.analyze`` populates the
``kb_characters`` variable in the ``PromptContext.extra`` dict with real
character data from the KB repository, so the coreference model can map
pronouns → characters (the empty-string gap described in the
``CoreferenceService`` adoption note).

Covers:

- ``kb_characters`` populated when ``kb_repo`` is wired and KB has
  ``character`` entries (non-character entity types filtered out).
- ``kb_characters`` empty when ``kb_repo=None`` (graceful degradation,
  backward compatibility — the constructor parameter is optional, so all
  pre-existing tests that omit it keep working).
- ``kb_characters`` empty when the KB fetch raises (RULE-11: log a
  warning and continue with an empty string; coreference can still run,
  just less accurately).
- The constructor accepts and stores ``kb_repo``.
- Character ``body`` text is truncated to keep the prompt bounded.

See:
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-11 (graceful degradation).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._coreference_test_helpers import (
    FakeComposer,
    consume,
    make_agent_output,
    make_chapter,
    make_kb_entry,
    make_novel,
    make_service,
    patch_mode1,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


# ---------------------------------------------------------------------------
# kb_characters population
# ---------------------------------------------------------------------------


class TestKBCharactersPopulation:
    """``kb_characters`` is populated from the KB repository."""

    @pytest.mark.asyncio
    async def test_kb_characters_populated_when_repo_has_characters(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        kb_repo = AsyncMock()
        kb_repo.list_entries.return_value = (
            [
                make_kb_entry(entity_type="character", name="Alice", body="A brave hero."),
                make_kb_entry(entity_type="character", name="Bob", body="A mysterious stranger."),
                # Non-character entries must be filtered out — coreference
                # only needs the character name list.
                make_kb_entry(entity_type="location", name="Castle", body="A tall keep."),
            ],
            3,
        )

        service = make_service(composer, config, kb_repo=kb_repo)  # type: ignore[arg-type]
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None, "prompt_context must be supplied to compose_invocation."
        kb_chars = ctx.extra["kb_characters"]
        assert "Alice" in kb_chars, "kb_characters must list the Alice character."
        assert "Bob" in kb_chars, "kb_characters must list the Bob character."
        assert "Castle" not in kb_chars, (
            "kb_characters must exclude non-character entity types (location)."
        )

    @pytest.mark.asyncio
    async def test_kb_characters_empty_when_repo_is_none(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """kb_repo=None → graceful degradation (backward compat).

        Pre-existing tests and any caller that omits ``kb_repo`` must keep
        working: ``kb_characters`` falls back to an empty string so the
        template's variable substitution still succeeds.
        """
        service = make_service(composer, config)  # kb_repo omitted → None
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        assert ctx.extra["kb_characters"] == "", (
            "kb_characters must be empty when kb_repo is None (graceful degradation)."
        )

    @pytest.mark.asyncio
    async def test_kb_characters_empty_when_repo_raises(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """RULE-11: a KB fetch failure logs a warning and continues with
        an empty ``kb_characters`` (coreference can still run, just less
        accurately). The error must NOT propagate to the caller."""
        kb_repo = AsyncMock()
        kb_repo.list_entries.side_effect = RuntimeError("DB connection lost")

        service = make_service(composer, config, kb_repo=kb_repo)  # type: ignore[arg-type]
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            # Must NOT raise — the KB failure is swallowed per RULE-11.
            events = await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        # Analysis still completes (result + done events).
        assert len(events) == 2
        assert events[1].event == "done"

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        assert ctx.extra["kb_characters"] == "", (
            "kb_characters must be empty when the KB fetch raises (RULE-11)."
        )

    @pytest.mark.asyncio
    async def test_character_body_truncated_in_kb_characters(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """Character body text is bounded ([:200]) to keep the prompt
        from growing unboundedly on large KB entries."""
        long_body = "x" * 500
        kb_repo = AsyncMock()
        kb_repo.list_entries.return_value = (
            [
                make_kb_entry(entity_type="character", name="Alice", body=long_body),
            ],
            1,
        )

        service = make_service(composer, config, kb_repo=kb_repo)  # type: ignore[arg-type]
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        kb_chars = ctx.extra["kb_characters"]
        # The body is truncated to 200 chars; the full 500-char body must
        # not appear.
        assert "Alice" in kb_chars
        assert long_body not in kb_chars, "Character body must be truncated ([:200])."


# ---------------------------------------------------------------------------
# Constructor wiring
# ---------------------------------------------------------------------------


class TestCoreferenceServiceConstructor:
    """The constructor accepts and stores the optional ``kb_repo``."""

    def test_constructor_stores_kb_repo(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.analysis.coreference_service import CoreferenceService
        from tests.unit.api.analysis._coreference_test_helpers import FakeModelRegistry

        novel_repo = AsyncMock()
        chapter_repo = AsyncMock()
        kb_repo = AsyncMock()

        service = CoreferenceService(
            novel_repo=novel_repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=config,
            composer=composer,  # type: ignore[arg-type]
            kb_repo=kb_repo,  # type: ignore[arg-type]
        )

        assert service._kb_repo is kb_repo, "Constructor must store kb_repo."

    def test_constructor_defaults_kb_repo_to_none(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.analysis.coreference_service import CoreferenceService
        from tests.unit.api.analysis._coreference_test_helpers import FakeModelRegistry

        service = CoreferenceService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=config,
            composer=composer,  # type: ignore[arg-type]
        )

        assert service._kb_repo is None, "kb_repo must default to None (backward compatibility)."
