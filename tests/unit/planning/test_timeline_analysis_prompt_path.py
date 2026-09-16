"""Prompt-path compliance tests for TimelineAnalysisService (ADR-049).

Verifies the RULE-02b prompt-resolution contract for timeline analysis:
- The composed system prompt reaches the TimelineAgent CONSTRUCTOR (pydantic-ai
  binds ``system_prompt`` at construction, not at run-time).
- The agent run prompt carries chapter data (runtime input) and does NOT
  contain the old inline feature framing ("Analyze the timeline for ...").
- The premature ADR-048 Mode 2 ``_TIMELINE_ANALYSIS_INJECTION`` declaration
  and ``ManualInjectionDeclaration`` import are absent (ADR-049 D10).

Behavioural tests live in ``test_timeline_analysis_service.py`` (RULE-04 split).

See:
    ADR-049 — Prompt-Surface Identity & Path Contract Retrofit (FIND-011)
    ADR-046 — Prompt-Path-Compliance
    CONSTRAINTS.md RULE-02/02a/02b, RULE-11
"""

from __future__ import annotations

import inspect
import uuid
from unittest.mock import MagicMock, patch

import pytest

from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from tests.unit.planning._timeline_test_helpers import (
    FakeComposer,
    fake_agent_result,
    make_chapter,
    make_novel_model,
    make_static_resolution,
)

# ---------------------------------------------------------------------------
# Fixtures (minimal — behavioural fixtures live in the behavioural test file)
# ---------------------------------------------------------------------------


def _make_service(composer: FakeComposer) -> TimelineAnalysisService:
    from unittest.mock import AsyncMock

    return TimelineAnalysisService(
        novel_repo=AsyncMock(),
        chapter_repo=AsyncMock(),
        model_registry=AsyncMock(),
        model_resolution=make_static_resolution(),
        composer=composer,  # type: ignore[arg-type]
    )


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


# ---------------------------------------------------------------------------
# Channel separation: composed system → agent constructor; data → run prompt
# ---------------------------------------------------------------------------


class TestComposedPromptReachesAgent:
    async def test_composed_system_prompt_reaches_agent_constructor(
        self,
        composer: FakeComposer,
    ) -> None:
        """The composed system prompt must reach the TimelineAgent via its
        CONSTRUCTOR (``system_prompt=``), not via a run-time kwarg.

        pydantic-ai binds ``system_prompt`` at agent construction; passing it
        to ``run()`` is ineffective. The composed system prompt must therefore
        be supplied to ``TimelineAgent(model=..., system_prompt=...)``.
        """
        service = _make_service(composer)
        service._novel_repo.get_by_id.return_value = make_novel_model(id=uuid.uuid4())  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel.return_value = [make_chapter()]  # type: ignore[attr-defined]
        service._registry.get_model.return_value = MagicMock(spec=[])  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            from unittest.mock import AsyncMock

            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=fake_agent_result())
            MockAgent.return_value = mock_agent

            await service.generate_timeline(uuid.uuid4(), uuid.uuid4())

        # TimelineAgent must be constructed with the composed system prompt
        construct_kwargs = MockAgent.call_args.kwargs
        assert construct_kwargs.get("system_prompt") == "COMPOSED-TIMELINE-SYSTEM", (
            "TimelineAgent must be constructed with composed.system as its "
            "system_prompt (pydantic-ai binds system_prompt at construction, "
            "not at run-time)."
        )

    async def test_run_prompt_carries_chapter_data_not_feature_framing(
        self,
        composer: FakeComposer,
    ) -> None:
        """The agent run prompt must carry chapter data (runtime input,
        RULE-02a category 3) and must NOT contain the old inline feature
        framing ("Analyze the timeline for ...")."""
        service = _make_service(composer)
        service._novel_repo.get_by_id.return_value = make_novel_model(  # type: ignore[attr-defined]
            id=uuid.uuid4(), title="My Epic"
        )
        service._chapter_repo.list_by_novel.return_value = [  # type: ignore[attr-defined]
            make_chapter(position=0, title="The Awakening"),
        ]
        service._registry.get_model.return_value = MagicMock(spec=[])  # type: ignore[attr-defined]

        captured_prompt: dict[str, str] = {}

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            mock_agent = MagicMock(spec=["run"])

            async def capture_run(prompt: str, **_kwargs: object) -> object:
                captured_prompt["value"] = prompt
                return fake_agent_result()

            mock_agent.run = capture_run
            MockAgent.return_value = mock_agent

            await service.generate_timeline(uuid.uuid4(), uuid.uuid4())

        run_prompt = captured_prompt.get("value", "")

        # Runtime chapter data MUST be present in the user/run channel
        assert "The Awakening" in run_prompt, "Chapter data must reach the agent as the run prompt."

        # The old inline f-string feature framing MUST be gone (RULE-02a)
        assert "Analyze the timeline for" not in run_prompt, (
            "Inline feature-task framing ('Analyze the timeline for ...') must "
            "not appear in the run prompt — feature framing flows through the "
            "governed template via PromptComposer (ADR-049 D9)."
        )


# ---------------------------------------------------------------------------
# Regression (ADR-049 D10): no premature ADR-048 Mode 2 reference
# ---------------------------------------------------------------------------


class TestNoManualInjectionDeclaration:
    """ADR-049 D10: ``_TIMELINE_ANALYSIS_INJECTION`` and the
    ``ManualInjectionDeclaration`` reference must be removed. ADR-048 is
    Proposed; production code may not depend on its Mode 2 contract."""

    def test_no_manual_injection_declaration_in_service(self) -> None:
        """The service module must not DEFINE ``_TIMELINE_ANALYSIS_INJECTION``
        nor IMPORT ``ManualInjectionDeclaration`` (ADR-048 Mode 2 is
        premature). Historical mentions in docstrings are permitted — only
        actual symbol definition/import is forbidden."""
        from narrare.planning import timeline_analysis_service as module

        # The declaration object must not be defined as a module attribute.
        assert not hasattr(module, "_TIMELINE_ANALYSIS_INJECTION"), (
            "_TIMELINE_ANALYSIS_INJECTION must not be defined (ADR-049 D10)."
        )
        # ManualInjectionDeclaration must not be imported into the module
        # namespace (it is no longer used — the service is Mode 1).
        assert "ManualInjectionDeclaration" not in dir(module), (
            "ManualInjectionDeclaration must not be imported — the service is "
            "now Mode 1 (composer-driven), not Mode 2 (ADR-049 D10)."
        )
        # No call site may pass the Mode 2 ``manual_injection=`` kwarg.
        # ``safe_compose_invocation`` (the Mode 2 evidence helper) and
        # ``compose_invocation`` must not be invoked from this service.
        source = inspect.getsource(module)
        assert "safe_compose_invocation(" not in source, (
            "safe_compose_invocation (Mode 2 evidence helper) must not be "
            "called — the premature ADR-048 Mode 2 path is removed (D10)."
        )
        assert "manual_injection=" not in source, (
            "manual_injection= kwarg must not be passed (ADR-049 D10)."
        )

    def test_no_inline_feature_fstring_in_service(self) -> None:
        """The service must not assemble a feature/task prompt via f-string
        passed to agent.run (RULE-02 / ADR-049 FIND-011)."""
        from narrare.planning import timeline_analysis_service as module

        source = inspect.getsource(module)
        assert "Analyze the timeline for" not in source, (
            "The inline feature-prompt f-string must be removed — feature "
            "framing flows through PromptComposer (ADR-049 D9)."
        )
