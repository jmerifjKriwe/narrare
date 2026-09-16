"""Source-level compliance + RULE-11 tests for TimelineExtractionService (ADR-054).

Verifies the regression half of the ADR-054 D2 migration (D7/D8):

- The false ADR-048 Mode 2 ``_TIMELINE_EXTRACTION_INJECTION`` declaration and
  the ``ManualInjectionDeclaration`` import are absent (D7).
- No ``manual_injection=`` kwarg and no inline feature-prompt f-string in the
  service source (D7/D2).
- Invocation-composition failures propagate (RULE-11 / D8) instead of being
  silently swallowed by ``except Exception: logger.warning``.
- The service fails loudly when ``composer`` is missing (RULE-11 defensive
  guard).

Behavioural Mode 1 tests live in ``test_timeline_extraction_service.py``
(RULE-04 split).

See:
    ADR-054 — Inline Feature-Prompt Debt Migration (D7/D8)
    ADR-049 — Precedent (FIND-011 timeline migration)
    ADR-048 — Mode 1/Mode 2 invocation contract
    CONSTRAINTS.md RULE-02/02a/02b, RULE-11
"""

from __future__ import annotations

import inspect
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from tests.unit.api.planning._timeline_extraction_test_helpers import (
    FakeComposedInvocation,
    FakeComposer,
    FakeModelRegistry,
    make_agent_output,
    make_chapter,
    make_novel,
    make_service,
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
# Regression (ADR-054 D7): no false Mode 2 declaration / import
# ---------------------------------------------------------------------------


class TestNoManualInjectionDeclaration:
    """ADR-054 D7: ``_TIMELINE_EXTRACTION_INJECTION`` and the
    ``ManualInjectionDeclaration`` import must be removed."""

    def test_no_manual_injection_declaration_in_service(self) -> None:
        from narrare.planning import timeline_extraction_service as module

        assert not hasattr(module, "_TIMELINE_EXTRACTION_INJECTION"), (
            "_TIMELINE_EXTRACTION_INJECTION must not be defined (ADR-054 D7)."
        )
        assert "ManualInjectionDeclaration" not in dir(module), (
            "ManualInjectionDeclaration must not be imported — the service is "
            "now Mode 1 (composer-driven), not Mode 2 (ADR-054 D7)."
        )
        source = inspect.getsource(module)
        assert "manual_injection=" not in source, (
            "manual_injection= kwarg must not be passed (ADR-054 D7)."
        )

    def test_no_inline_feature_fstring_in_service(self) -> None:
        from narrare.planning import timeline_extraction_service as module

        source = inspect.getsource(module)
        # The removed inline f-string interpolated novel/chapter fields:
        #   f"Extract temporal expressions from the following "
        #   f"chapter of '{novel.title}':\n\n"
        # Assert that interpolated form is absent. (The method docstring
        # legitimately says "Extract temporal expressions from chapters ..."
        # — that is documentation, not prompt assembly, so it is permitted.)
        assert "Extract temporal expressions from the following" not in source, (
            "The inline feature-prompt f-string must be removed — feature "
            "framing flows through PromptComposer (ADR-054 D2)."
        )
        assert "chapter of '{novel.title}'" not in source, (
            "The inline novel-title interpolation must be removed from the run prompt (ADR-054 D2)."
        )


# ---------------------------------------------------------------------------
# RULE-11 (ADR-054 D8): composition failures propagate, not swallowed
# ---------------------------------------------------------------------------


class TestCompositionFailurePropagates:
    """ADR-054 D8 / RULE-11: invocation-composition errors must propagate.

    The previous ``except Exception: logger.warning`` around
    ``compose_invocation`` silently degraded to the inline f-string. Mode 1
    produces the prompt, so swallowing the failure would leave no prompt —
    the error must now raise.
    """

    @pytest.mark.asyncio
    async def test_compose_invocation_failure_propagates(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent"),
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(side_effect=RuntimeError("pipeline offline")),
            ),
            pytest.raises(RuntimeError, match="pipeline offline"),
        ):
            results = []
            async for event in service.stream_extraction(  # type: ignore[arg-type]
                uuid.uuid4(), uuid.uuid4(), None
            ):
                results.append(event)


# ---------------------------------------------------------------------------
# Defensive guards: missing composer fails loudly (RULE-11)
# ---------------------------------------------------------------------------


class TestDefensiveGuards:
    """The service must fail loudly (RULE-11) when the composer is missing,
    rather than silently falling back to inline assembly."""

    @pytest.mark.asyncio
    async def test_missing_composer_raises_configuration_error(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.planning.timeline_extraction_service import TimelineExtractionService
        from narrare_core.shared.errors import ConfigurationError

        service = TimelineExtractionService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_resolution=StaticModelResolution(
                ResolvedModel(config=config, api_key=None, base_url=None, source="unit-test")
            ),
            composer=None,
        )
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with pytest.raises(ConfigurationError, match="PromptComposer"):
            results = []
            async for event in service.stream_extraction(  # type: ignore[arg-type]
                uuid.uuid4(), uuid.uuid4(), None
            ):
                results.append(event)


# ---------------------------------------------------------------------------
# Run-prompt channel separation (ADR-054 D2 regression)
# ---------------------------------------------------------------------------


class TestRunPromptChannelSeparation:
    """ADR-054 D2: feature framing flows through the governed template via
    PromptComposer (RULE-02a); only chapter content (runtime data) may appear
    in the agent run prompt."""

    @pytest.mark.asyncio
    async def test_run_prompt_does_not_contain_inline_feature_framing(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """The agent run prompt must NOT contain the old inline feature
        framing ("Extract temporal expressions ..."). Feature framing flows
        through the governed template via PromptComposer (RULE-02a). Only the
        chapter content (runtime data) may appear in the run prompt."""
        from unittest.mock import MagicMock, patch

        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel(  # type: ignore[attr-defined]
            title="My Epic"
        )

        captured: list[str] = []

        with (
            patch(
                "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent"
            ) as MockAgent,
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation(user="")),
            ),
        ):
            mock_agent = MagicMock(spec=["run"])

            async def capture_run(prompt: str, **_kwargs: object) -> object:
                captured.append(prompt)
                return make_agent_output()

            mock_agent.run = capture_run  # type: ignore[assignment]
            MockAgent.return_value = mock_agent

            async for _ in service.stream_extraction(uuid.uuid4(), uuid.uuid4(), None):  # type: ignore[arg-type]
                pass

        assert captured, "agent.run was never called"
        for run_prompt in captured:
            assert "Extract temporal expressions" not in run_prompt, (
                "Inline feature-task framing ('Extract temporal expressions ...') "
                "must not appear in the run prompt — feature framing flows through "
                "the governed template via PromptComposer (ADR-054 D2)."
            )

    @pytest.mark.asyncio
    async def test_chapter_content_is_runtime_data_in_run_prompt(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """The per-chapter content (title/position/summary) is category-3
        runtime data and must flow as the run prompt (user channel), not be
        baked into the system template."""
        from unittest.mock import MagicMock, patch

        chapter = make_chapter(
            position=2, title="The Arrival", summary="Three days later, the hero arrived."
        )
        service = make_service(composer, config, chapters=[chapter])
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        captured: list[str] = []

        with (
            patch(
                "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent"
            ) as MockAgent,
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation(user="")),
            ),
        ):
            mock_agent = MagicMock(spec=["run"])

            async def capture_run(prompt: str, **_kwargs: object) -> object:
                captured.append(prompt)
                return make_agent_output()

            mock_agent.run = capture_run  # type: ignore[assignment]
            MockAgent.return_value = mock_agent

            async for _ in service.stream_extraction(uuid.uuid4(), uuid.uuid4(), None):  # type: ignore[arg-type]
                pass

        assert captured, "agent.run was never called"
        # The chapter content (runtime data) must appear in the run prompt
        assert any("The Arrival" in p for p in captured), (
            "Chapter title (runtime data) must appear in the run prompt."
        )
        assert any("Three days later" in p for p in captured), (
            "Chapter content (runtime data) must appear in the run prompt."
        )
