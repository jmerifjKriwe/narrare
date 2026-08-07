"""Subclass-override error classification regression suite (issue #156 / AUFG-03-06).

Verifies that every real ``NarrareAgent`` subclass which overrides ``run()`` or
``run_phase1()`` funnels failures through ``NarrareAgent.run()``'s try/except +
``classify_error()`` block (via ``super().run()``), so raw pydantic-ai
exceptions never leak past the agent boundary.

Before the fix, these overrides called ``self._agent.run(...)`` directly with a
``cast()``, bypassing classification — so raw provider exceptions leaked.
After the fix they delegate to ``super().run()``, which applies the single
translation point.

This is the subclass-override regression suite for the AUFG-03-06 enforcement
of the single error-translation point. Split out of
``test_agent_error_classification.py`` to respect RULE-04 (file-size limit);
see ``scripts/check_architecture.py``.

The ``make_error_model`` fixture is shared via ``conftest.py``.
"""

from __future__ import annotations

import pytest
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
)
from pydantic_ai.models.test import TestModel

from narrare_core.agents.band_summary_agent import BandSummaryAgent
from narrare_core.agents.band_summary_types import BandSummaryDeps
from narrare_core.agents.beta_reader_agent import BetaReaderAgent
from narrare_core.agents.beta_reader_types import BetaReaderDeps
from narrare_core.agents.consistency_agent import ConsistencyAgent
from narrare_core.agents.consistency_types import ConsistencyDeps
from narrare_core.agents.dialogue_coach_agent import DialogueCoachAgent
from narrare_core.agents.dialogue_coach_types import DialogueCoachDeps
from narrare_core.agents.draft_agent import DraftAgent
from narrare_core.agents.draft_types import DraftDeps
from narrare_core.agents.errors import (
    AgentError,
    AgentTimeoutError,
    ModelExecutionError,
    ModelRetryExhaustedError,
)
from narrare_core.agents.prompt_live_test_agent import (
    PromptLiveTestAgent,
    PromptLiveTestDeps,
    PromptLiveTestResult,
)
from narrare_core.agents.series_consistency_agent import SeriesConsistencyAgent
from narrare_core.agents.series_consistency_types import SeriesConsistencyDeps

# ---------------------------------------------------------------------------
# Subclass-override error classification (AUFG-03-06 — single translation point)
#
# Regression coverage for the subclass override path: every NarrareAgent
# subclass that overrides run()/run_phase1() MUST funnel through
# NarrareAgent.run()'s try/except + classify_error() block (via super().run()),
# so raw pydantic-ai exceptions never leak past the agent boundary. Before the
# fix these overrides called self._agent.run(...) directly with a cast(),
# bypassing classification — so raw exceptions leaked.
# ---------------------------------------------------------------------------


def _assert_typed_error(
    exc: AgentError,
    *,
    expected_cls: type[AgentError],
    expected_error_type: str,
    raw_exc: BaseException,
    raw_exc_cls: type[BaseException],
    agent_name_substr: str,
    provider_code: str | None = None,
) -> None:
    """Standard assertions for a classified subclass-override error.

    Verifies the five invariants that prove the error was translated at the
    agent boundary (not leaked raw from the provider):

    (a) it is an instance of the expected typed AgentError subtype,
    (b) it is an AgentError AND NOT the raw provider exception (no raw leak),
    (c) error_type matches expectation,
    (d) .original is the injected exception,
    (e) agent_name carries the subclass qualified name (type(self).__qualname__
        flowed through super().run()).
    """
    assert isinstance(exc, expected_cls), (
        f"expected {expected_cls.__name__}, got {type(exc).__name__}"
    )
    assert isinstance(exc, AgentError), "must be an AgentError subtype"
    assert not isinstance(exc, raw_exc_cls), (
        f"raw {raw_exc_cls.__name__} leaked past the agent boundary"
    )
    assert exc.error_type == expected_error_type
    assert exc.original is raw_exc, ".original must be the injected exception"
    assert agent_name_substr in exc.agent_name, (
        f"{agent_name_substr!r} not in agent_name={exc.agent_name!r}"
    )
    if provider_code is not None:
        assert exc.provider_code == provider_code  # type: ignore[attr-defined]


class TestSubclassOverrideErrorClassification:
    """Real subclasses with run()/run_phase1() overrides must classify errors.

    Each test instantiates a REAL NarrareAgent subclass (not _SimpleAgent) and
    injects a failure via FunctionModel, exercising the override → super().run()
    translation path. Before the fix, the raw pydantic-ai exception leaked
    because the override called ``self._agent.run(...)`` directly, bypassing
    ``NarrareAgent.run()``'s try/except + classify_error() block.
    """

    async def test_consistency_agent_run_classifies_model_http_error(
        self,
        make_error_model,
    ) -> None:
        """ConsistencyAgent.run() → ModelHTTPError(500) → ModelExecutionError."""
        raw = ModelHTTPError(status_code=500, model_name="test-model")
        agent = ConsistencyAgent(model=make_error_model(raw))

        with pytest.raises(ModelExecutionError) as exc_info:
            await agent.run("check", deps=ConsistencyDeps())

        _assert_typed_error(
            exc_info.value,
            expected_cls=ModelExecutionError,
            expected_error_type="model_execution",
            raw_exc=raw,
            raw_exc_cls=ModelHTTPError,
            agent_name_substr="ConsistencyAgent",
            provider_code="HTTP_500",
        )

    async def test_draft_agent_run_classifies_timeout(
        self,
        make_error_model,
    ) -> None:
        """DraftAgent.run() → TimeoutError → AgentTimeoutError."""
        raw = TimeoutError()
        agent = DraftAgent(model=make_error_model(raw))

        with pytest.raises(AgentTimeoutError) as exc_info:
            await agent.run("draft", deps=DraftDeps())

        _assert_typed_error(
            exc_info.value,
            expected_cls=AgentTimeoutError,
            expected_error_type="agent_timeout",
            raw_exc=raw,
            raw_exc_cls=TimeoutError,
            agent_name_substr="DraftAgent",
        )

    async def test_series_consistency_agent_run_classifies_retry_exhausted(
        self,
        make_error_model,
    ) -> None:
        """SeriesConsistencyAgent.run() → UnexpectedModelBehavior(retry).

        Maps to ModelRetryExhaustedError.
        """
        raw = UnexpectedModelBehavior("too many retries exhausted")
        agent = SeriesConsistencyAgent(model=make_error_model(raw))

        with pytest.raises(ModelRetryExhaustedError) as exc_info:
            await agent.run("check series", deps=SeriesConsistencyDeps())

        _assert_typed_error(
            exc_info.value,
            expected_cls=ModelRetryExhaustedError,
            expected_error_type="model_retry_exhausted",
            raw_exc=raw,
            raw_exc_cls=UnexpectedModelBehavior,
            agent_name_substr="SeriesConsistencyAgent",
        )

    async def test_band_summary_agent_run_classifies_model_api_error(
        self,
        make_error_model,
    ) -> None:
        """BandSummaryAgent.run() → ModelAPIError → ModelExecutionError."""
        raw = ModelAPIError(model_name="test-model", message="rate limited")
        agent = BandSummaryAgent(model=make_error_model(raw))

        with pytest.raises(ModelExecutionError) as exc_info:
            await agent.run("summarise", deps=BandSummaryDeps())

        _assert_typed_error(
            exc_info.value,
            expected_cls=ModelExecutionError,
            expected_error_type="model_execution",
            raw_exc=raw,
            raw_exc_cls=ModelAPIError,
            agent_name_substr="BandSummaryAgent",
        )

    async def test_dialogue_coach_agent_post_process_classifies_http_error(
        self,
        make_error_model,
    ) -> None:
        """DialogueCoachAgent.run() (post-process) → ModelHTTPError(429) → ModelExecutionError.

        Proves the POST_PROCESS post-filter does NOT swallow classification:
        the error is raised by super().run() before the filter even runs.
        """
        raw = ModelHTTPError(status_code=429, model_name="test-model")
        agent = DialogueCoachAgent(model=make_error_model(raw))

        with pytest.raises(ModelExecutionError) as exc_info:
            await agent.run(
                "analyse",
                deps=DialogueCoachDeps(text_to_analyze='"hi."', mode="analyze"),
            )

        _assert_typed_error(
            exc_info.value,
            expected_cls=ModelExecutionError,
            expected_error_type="model_execution",
            raw_exc=raw,
            raw_exc_cls=ModelHTTPError,
            agent_name_substr="DialogueCoachAgent",
            provider_code="HTTP_429",
        )

    async def test_prompt_live_test_agent_post_process_classifies_behavior_error(
        self,
        make_error_model,
    ) -> None:
        """PromptLiveTestAgent.run() (post-process, OutputT lie) → ModelExecutionError.

        UnexpectedModelBehavior without retry keywords → ModelExecutionError.
        Proves the cast('str', ...) wrapper does not swallow classification.
        """
        raw = UnexpectedModelBehavior("content filter blocked the response")
        agent = PromptLiveTestAgent(model=make_error_model(raw))

        with pytest.raises(ModelExecutionError) as exc_info:
            await agent.run(
                "preview",
                deps=PromptLiveTestDeps(
                    composed_system="You are a narrator.",
                    composed_user="Continue.",
                    language="en",
                ),
            )

        _assert_typed_error(
            exc_info.value,
            expected_cls=ModelExecutionError,
            expected_error_type="model_execution",
            raw_exc=raw,
            raw_exc_cls=UnexpectedModelBehavior,
            agent_name_substr="PromptLiveTestAgent",
        )

    async def test_beta_reader_agent_run_phase1_classifies_http_error(
        self,
        make_error_model,
    ) -> None:
        """BetaReaderAgent.run_phase1() (non-run method name) → ModelExecutionError.

        The delegating call lives in run_phase1, not run. super().run() still
        applies classification via type(self).__qualname__.
        """
        raw = ModelHTTPError(status_code=500, model_name="test-model")
        agent = BetaReaderAgent(model=make_error_model(raw))

        with pytest.raises(ModelExecutionError) as exc_info:
            await agent.run_phase1("analyse chapter", deps=BetaReaderDeps())

        _assert_typed_error(
            exc_info.value,
            expected_cls=ModelExecutionError,
            expected_error_type="model_execution",
            raw_exc=raw,
            raw_exc_cls=ModelHTTPError,
            agent_name_substr="BetaReaderAgent",
            provider_code="HTTP_500",
        )

    # ------------------------------------------------------------------
    # Happy-path smokes — pin POST_PROCESS behaviour survives the refactor
    # (these pass before AND after the fix; they guard success-path semantics)
    # ------------------------------------------------------------------

    async def test_dialogue_coach_agent_post_filter_still_drops_empty_quotes(self) -> None:
        """POST_PROCESS post-filter still drops whitespace-only original_quote."""
        issues = [
            {
                "issue_type": "redundancy",
                "speaker": "",
                "original_quote": "valid quote",  # survives
                "diagnosis": "x",
                "severity": "low",
            },
            {
                "issue_type": "redundancy",
                "speaker": "",
                "original_quote": "   ",  # whitespace-only — dropped by post-filter
                "diagnosis": "y",
                "severity": "low",
            },
        ]
        model = TestModel(
            custom_output_args={"issues": issues, "adaptive_summary": ""},
        )
        agent = DialogueCoachAgent(model=model)
        result = await agent.run(
            "analyse",
            deps=DialogueCoachDeps(text_to_analyze='"hi."', mode="analyze"),
        )

        assert len(result.issues) == 1
        assert result.issues[0].original_quote == "valid quote"

    async def test_prompt_live_test_agent_still_wraps_str_in_result(self) -> None:
        """POST_PROCESS wrapper still returns PromptLiveTestResult(text=...)."""
        model = TestModel(custom_output_text="Free-form preview prose.")
        agent = PromptLiveTestAgent(model=model)
        result = await agent.run(
            "preview",
            deps=PromptLiveTestDeps(
                composed_system="You are a narrator.",
                composed_user="Continue.",
                language="en",
            ),
        )

        assert isinstance(result, PromptLiveTestResult)
        assert result.text == "Free-form preview prose."
