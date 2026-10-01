"""Unit tests for core/llm/dynamic_tiering.py (ADR-089 pilot, Task 7).

Implements the ADR-089 Test Contract items owned by the Core module:

* Pure policy — both triggers, boundaries (``>`` vs ``>=``), ``None``
  prompt, degraded short-circuit.
* Derivation — synthesized ``ModelMessage`` histories → ``turn_count``;
  ``str`` / ``Sequence[UserContent]`` / ``None`` prompts →
  ``latest_user_prompt``.
* Factory — ``build_tiered_model`` returns the upstream ``SelectModel``
  capability; the selector picks base/escalation; degraded mode always
  selects base; one ``dynamic_tier_escalation`` event per escalated turn.
* End-to-end selection — two ``TestModel`` instances with distinct
  outputs prove the escalated turn actually used the escalation model.
* RULE-18b knob evidence — the three ``CoreSettings`` fields resolve
  from env and flip the escalation decision.

See: docs/architecture/decisions/ADR-089-dynamic-tier-routing-selectmodel.md
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.capabilities import SelectModel
from pydantic_ai.messages import (
    ImageUrl,
    ModelRequest,
    ModelResponse,
    TextContent,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel
from structlog.testing import capture_logs

from narrare_core.llm.dynamic_tiering import (
    TieringPolicy,
    build_tiered_model,
    latest_user_prompt,
    should_escalate,
    turn_count,
)
from narrare_core.settings import CoreSettings, get_core_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai.messages import ModelMessage, UserContent

# ---------------------------------------------------------------------------
# Helpers — synthesized pydantic-ai message histories (no I/O, no LLM)
# ---------------------------------------------------------------------------

_TIERING_ENV_VARS = (
    "NARRARE_LLM_DYNAMIC_TIERING",
    "NARRARE_LLM_DYNAMIC_TIERING_MAX_PROMPT_CHARS",
    "NARRARE_LLM_DYNAMIC_TIERING_MIN_TURNS",
)


def _user_prompt(content: str | Sequence[UserContent]) -> ModelRequest:
    """Build a ModelRequest with a single UserPromptPart."""
    return ModelRequest(parts=[UserPromptPart(content=content)])


def _model_response() -> ModelResponse:
    """Build a minimal ModelResponse (non-request message in a history)."""
    return ModelResponse(parts=[TextPart(content="model reply")])


def _selection_context(
    prompt: str | Sequence[UserContent] | None,
    messages: Sequence[ModelMessage],
) -> Any:
    """Duck-typed ``ModelSelectionContext`` for direct selector calls.

    The selector reads only ``.prompt`` and ``.messages`` (ADR-089
    Decision 3); a ``SimpleNamespace`` avoids constructing the full
    upstream context (agent/deps/usage) just for unit-level selection
    checks. End-to-end selection is covered separately with a real Agent.
    """
    return SimpleNamespace(prompt=prompt, messages=messages)


# ---------------------------------------------------------------------------
# TieringPolicy — frozen value object with ADR-pinned defaults
# ---------------------------------------------------------------------------


class TestTieringPolicy:
    def test_policy_defaults_match_adr_089_decision_3(self) -> None:
        policy = TieringPolicy()
        assert policy.max_prompt_chars == 2000
        assert policy.min_turns == 6

    def test_policy_is_frozen(self) -> None:
        policy = TieringPolicy()
        # The assignment is deliberately invalid: pyright enforces the
        # frozen dataclass's read-only attributes statically (reportAttribute
        # AccessIssue), so it goes through an Any-typed view — the test
        # asserts the *runtime* enforcement (FrozenInstanceError), not the
        # static one.
        mutable: Any = policy
        with pytest.raises(FrozenInstanceError):
            mutable.max_prompt_chars = 1


# ---------------------------------------------------------------------------
# should_escalate — pure policy (ADR-089 Decision 3)
# ---------------------------------------------------------------------------


class TestShouldEscalate:
    def test_short_prompt_low_turns_stays_on_base(self) -> None:
        assert (
            should_escalate(latest_user_prompt="hello", turn_count=1, policy=TieringPolicy())
            is False
        )

    def test_prompt_length_boundary_is_strictly_greater(self) -> None:
        policy = TieringPolicy(max_prompt_chars=2000, min_turns=99)
        assert should_escalate(latest_user_prompt="x" * 2000, turn_count=1, policy=policy) is False
        assert should_escalate(latest_user_prompt="x" * 2001, turn_count=1, policy=policy) is True

    def test_turn_count_boundary_is_at_least(self) -> None:
        policy = TieringPolicy(max_prompt_chars=999_999, min_turns=6)
        assert should_escalate(latest_user_prompt="hi", turn_count=5, policy=policy) is False
        assert should_escalate(latest_user_prompt="hi", turn_count=6, policy=policy) is True

    def test_none_prompt_disables_length_trigger_only(self) -> None:
        """ADR-089 Decision 3 clarification: None prompt → length trigger false."""
        policy = TieringPolicy(max_prompt_chars=10, min_turns=99)
        assert should_escalate(latest_user_prompt=None, turn_count=1, policy=policy) is False
        # The turn trigger still fires with a None prompt.
        assert should_escalate(latest_user_prompt=None, turn_count=99, policy=policy) is True

    def test_empty_prompt_string_never_escalates_on_length(self) -> None:
        policy = TieringPolicy(max_prompt_chars=0, min_turns=99)
        # len("") > 0 is False — only turns escalate.
        assert should_escalate(latest_user_prompt="", turn_count=1, policy=policy) is False


# ---------------------------------------------------------------------------
# latest_user_prompt — derivation from ModelSelectionContext fields
# ---------------------------------------------------------------------------


class TestLatestUserPrompt:
    def test_str_prompt_returned_as_is(self) -> None:
        assert latest_user_prompt("direct question", []) == "direct question"

    def test_sequence_prompt_joins_text_items_with_single_space(self) -> None:
        prompt: list[UserContent] = [
            "first",
            TextContent(content="second"),
            ImageUrl(url="https://example.com/image.png"),
        ]
        assert latest_user_prompt(prompt, []) == "first second"

    def test_sequence_prompt_without_text_items_is_empty(self) -> None:
        prompt: list[UserContent] = [ImageUrl(url="https://example.com/image.png")]
        assert latest_user_prompt(prompt, []) == ""

    def test_none_prompt_falls_back_to_last_model_request_text(self) -> None:
        messages = [
            _user_prompt("old question"),
            _model_response(),
            _user_prompt("newest question"),
        ]
        assert latest_user_prompt(None, messages) == "newest question"

    def test_none_prompt_fallback_joins_last_request_sequence_content(self) -> None:
        messages = [
            _user_prompt("first request"),
            _user_prompt(["alpha", TextContent(content="beta")]),
        ]
        assert latest_user_prompt(None, messages) == "alpha beta"

    def test_none_prompt_without_model_request_returns_empty(self) -> None:
        assert latest_user_prompt(None, []) == ""
        assert latest_user_prompt(None, [_model_response()]) == ""


# ---------------------------------------------------------------------------
# turn_count — derivation from ModelSelectionContext.messages
# ---------------------------------------------------------------------------


class TestTurnCount:
    def test_counts_model_requests_only(self) -> None:
        messages = [
            _user_prompt("q1"),
            _model_response(),
            _user_prompt("q2"),
            _model_response(),
            _user_prompt("q3"),
        ]
        assert turn_count(messages) == 3

    def test_empty_history_is_zero(self) -> None:
        assert turn_count([]) == 0


# ---------------------------------------------------------------------------
# build_tiered_model — SelectModel capability factory (ADR-089 Decision 1)
# ---------------------------------------------------------------------------


class TestBuildTieredModel:
    def test_factory_returns_select_model_capability(self) -> None:
        capability = build_tiered_model(TestModel(), TestModel(), policy=TieringPolicy())
        assert isinstance(capability, SelectModel)

    def test_selector_returns_base_below_thresholds(self) -> None:
        base, escalation = TestModel(), TestModel()
        capability = build_tiered_model(base, escalation, policy=TieringPolicy())
        selector = capability.get_model()
        context = _selection_context("hi", [_user_prompt("hi")])
        assert selector(context) is base

    def test_selector_returns_escalation_on_long_prompt(self) -> None:
        base, escalation = TestModel(), TestModel()
        capability = build_tiered_model(base, escalation, policy=TieringPolicy())
        selector = capability.get_model()
        context = _selection_context("x" * 2001, [_user_prompt("x" * 2001)])
        assert selector(context) is escalation

    def test_selector_returns_escalation_on_turn_count(self) -> None:
        base, escalation = TestModel(), TestModel()
        capability = build_tiered_model(base, escalation, policy=TieringPolicy())
        selector = capability.get_model()
        messages = [_user_prompt(f"q{i}") for i in range(6)]
        context = _selection_context("hi", messages)
        assert selector(context) is escalation

    def test_degraded_mode_escalation_none_always_selects_base(self) -> None:
        """ADR-089 Decision 1/5: escalation_model=None → always base, branch-free."""
        base = TestModel()
        capability = build_tiered_model(base, None, policy=TieringPolicy())
        selector = capability.get_model()
        long_prompt = _selection_context("x" * 5000, [])
        many_turns = _selection_context("hi", [_user_prompt("q") for _ in range(50)])
        assert selector(long_prompt) is base
        assert selector(many_turns) is base

    def test_escalated_turn_logs_one_dynamic_tier_escalation_event(self) -> None:
        base, escalation = TestModel(), TestModel()
        policy = TieringPolicy(max_prompt_chars=2000, min_turns=99)
        capability = build_tiered_model(base, escalation, policy=policy)
        selector = capability.get_model()
        with capture_logs() as logs:
            selector(_selection_context("x" * 2001, [_user_prompt("x" * 2001)]))
        events = [entry for entry in logs if entry["event"] == "dynamic_tier_escalation"]
        assert len(events) == 1
        event = events[0]
        assert event["reason"] == "prompt_chars"
        assert event["prompt_chars"] == 2001
        assert event["turn_count"] == 1
        assert event["max_prompt_chars"] == policy.max_prompt_chars
        assert event["min_turns"] == policy.min_turns
        # Model ids are part of the evaluation signal (Decision 7). Provider
        # attribution stays with the wiring layer (Model ABC has only
        # model_name — verified against pydantic-ai 2.52).
        assert event["base_model_id"] == base.model_name
        assert event["escalation_model_id"] == escalation.model_name

    def test_min_turns_trigger_logs_reason_min_turns(self) -> None:
        base, escalation = TestModel(), TestModel()
        capability = build_tiered_model(
            base, escalation, policy=TieringPolicy(max_prompt_chars=999_999, min_turns=6)
        )
        messages = [_user_prompt(f"q{i}") for i in range(6)]
        with capture_logs() as logs:
            capability.get_model()(_selection_context("hi", messages))
        events = [entry for entry in logs if entry["event"] == "dynamic_tier_escalation"]
        assert len(events) == 1
        assert events[0]["reason"] == "min_turns"
        assert events[0]["turn_count"] == 6

    def test_base_turn_logs_no_escalation_event(self) -> None:
        base, escalation = TestModel(), TestModel()
        capability = build_tiered_model(base, escalation, policy=TieringPolicy())
        with capture_logs() as logs:
            capability.get_model()(_selection_context("hi", [_user_prompt("hi")]))
        assert not [entry for entry in logs if entry["event"] == "dynamic_tier_escalation"]


# ---------------------------------------------------------------------------
# End-to-end selection with a real Agent (ADR-089 Test Contract: "Selection")
# ---------------------------------------------------------------------------


class TestAgentSelectionEndToEnd:
    async def test_short_turn_uses_base_model_and_long_turn_escalates(self) -> None:
        """Two TestModels with distinct outputs prove which model ran.

        The constructor model is the base tier; the capability's selection
        wins over it (verified upstream: only run-time ``model=`` overrides
        are authoritative — ADR-089 Decision 7).
        """
        base = TestModel(custom_output_text="base-response")
        escalation = TestModel(custom_output_text="escalation-response")
        policy = TieringPolicy(max_prompt_chars=10, min_turns=99)
        agent = Agent(
            model=base,
            capabilities=[build_tiered_model(base, escalation, policy=policy)],
        )

        short_result = await agent.run("short")
        assert short_result.output == "base-response"

        long_result = await agent.run("this prompt is long")
        assert long_result.output == "escalation-response"


# ---------------------------------------------------------------------------
# RULE-18b knob evidence — the three CoreSettings fields (ADR-089 Decision 2)
# ---------------------------------------------------------------------------


class TestDynamicTieringSettingsKnobs:
    def test_defaults_are_off_and_adr_pinned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in _TIERING_ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        settings = CoreSettings()
        assert settings.llm_dynamic_tiering_enabled is False
        assert settings.llm_dynamic_tiering_max_prompt_chars == 2000
        assert settings.llm_dynamic_tiering_min_turns == 6

    def test_env_overrides_resolve_through_cached_accessor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NARRARE_LLM_DYNAMIC_TIERING", "true")
        monkeypatch.setenv("NARRARE_LLM_DYNAMIC_TIERING_MAX_PROMPT_CHARS", "10")
        monkeypatch.setenv("NARRARE_LLM_DYNAMIC_TIERING_MIN_TURNS", "3")
        get_core_settings.cache_clear()
        try:
            settings = get_core_settings()
            assert settings.llm_dynamic_tiering_enabled is True
            assert settings.llm_dynamic_tiering_max_prompt_chars == 10
            assert settings.llm_dynamic_tiering_min_turns == 3
        finally:
            get_core_settings.cache_clear()

    def test_max_prompt_chars_knob_flips_escalation_decision(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RULE-18b effect evidence: changing the knob changes the decision."""
        prompt = "x" * 11
        monkeypatch.delenv("NARRARE_LLM_DYNAMIC_TIERING_MAX_PROMPT_CHARS", raising=False)
        get_core_settings.cache_clear()
        try:
            default_policy = TieringPolicy(
                max_prompt_chars=get_core_settings().llm_dynamic_tiering_max_prompt_chars,
                min_turns=99,
            )
            monkeypatch.setenv("NARRARE_LLM_DYNAMIC_TIERING_MAX_PROMPT_CHARS", "10")
            get_core_settings.cache_clear()
            tuned_policy = TieringPolicy(
                max_prompt_chars=get_core_settings().llm_dynamic_tiering_max_prompt_chars,
                min_turns=99,
            )
        finally:
            get_core_settings.cache_clear()
        assert (
            should_escalate(latest_user_prompt=prompt, turn_count=1, policy=default_policy) is False
        )
        assert should_escalate(latest_user_prompt=prompt, turn_count=1, policy=tuned_policy) is True

    def test_min_turns_knob_flips_escalation_decision(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("NARRARE_LLM_DYNAMIC_TIERING_MIN_TURNS", raising=False)
        get_core_settings.cache_clear()
        try:
            default_policy = TieringPolicy(
                max_prompt_chars=999_999,
                min_turns=get_core_settings().llm_dynamic_tiering_min_turns,
            )
            monkeypatch.setenv("NARRARE_LLM_DYNAMIC_TIERING_MIN_TURNS", "2")
            get_core_settings.cache_clear()
            tuned_policy = TieringPolicy(
                max_prompt_chars=999_999,
                min_turns=get_core_settings().llm_dynamic_tiering_min_turns,
            )
        finally:
            get_core_settings.cache_clear()
        assert (
            should_escalate(latest_user_prompt="hi", turn_count=2, policy=default_policy) is False
        )
        assert should_escalate(latest_user_prompt="hi", turn_count=2, policy=tuned_policy) is True
