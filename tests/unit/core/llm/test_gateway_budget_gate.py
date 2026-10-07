"""ModelRegistry.get_model() pre-call budget gate — ADR-094 (STATS-002).

The gate sits at the TOP of ``get_model()`` — the single upstream choke
point covering BOTH ADR-093 LLM populations: the registry path
(``run()``/``stream()`` via registry_run.py) and the capability path
(``prepare()``).  Unlike the usage-event sink seam (ADR-093 D1 — never
raise), this seam MAY raise: ``BudgetExceededError`` stops the run
BEFORE any provider resolution or spend occurs.  Unset guard or missing
user attribution (``usage_user_id`` is None) ⇒ no-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.budget import set_budget_guard
from narrare_core.llm.usage_events import set_usage_context
from narrare_core.shared.errors import BudgetExceededError

if TYPE_CHECKING:
    from collections.abc import Generator
    from uuid import UUID

    from pydantic_ai.models.test import TestModel

    from narrare_core.llm.gateway import ModelRegistry


class OverBudgetGuard:
    """Fake BudgetGuard that always blocks (mirrors test_budget.py)."""

    def __init__(self) -> None:
        self.checked: list[UUID] = []

    def check(self, user_id: UUID) -> None:
        self.checked.append(user_id)
        raise BudgetExceededError(user_id, month_spend_usd=12.5, monthly_budget_usd=10.0)


@pytest.fixture(autouse=True)
def _clean_budget_seam() -> Generator[None]:
    """Isolate the guard slot AND usage attribution ContextVars per test."""
    set_budget_guard(None)
    set_usage_context(user_id=None, novel_id=None)
    yield
    set_budget_guard(None)
    set_usage_context(user_id=None, novel_id=None)


def _arm_over_budget_guard() -> OverBudgetGuard:
    guard = OverBudgetGuard()
    set_budget_guard(guard)
    return guard


def _set_user() -> UUID:
    """Put a user into the usage attribution ContextVar; return its UUID."""
    user = uuid4()
    set_usage_context(user_id=user, novel_id=None)
    return user


def _patch_provider_sentinel(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the provider lookup with a sentinel that must NEVER run.

    Patched at the point of use (``gateway.get_provider``) — same target
    as the ``registry_with_test_model`` fixture, because ``from X import
    get as get_provider`` creates a local binding.  If the gate fails to
    fire, the sentinel raises loudly instead of resolving a provider.
    """
    calls: list[str] = []

    def _must_not_run(provider_name: str) -> object:
        calls.append(provider_name)
        raise AssertionError(
            f"provider resolution must not run when over budget (got {provider_name!r})"
        )

    monkeypatch.setattr("narrare_core.llm.gateway.get_provider", _must_not_run)
    return calls


class TestGetModelBudgetGate:
    """get_model() raises BudgetExceededError before ANY provider work."""

    async def test_over_budget_user_raises_before_provider_resolution(
        self,
        registry: ModelRegistry,
        write_config: ResolvedModelConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Guard set + over budget + user in ContextVar => raise, provider untouched."""
        provider_calls = _patch_provider_sentinel(monkeypatch)
        guard = _arm_over_budget_guard()
        user = _set_user()

        with pytest.raises(BudgetExceededError) as exc_info:
            await registry.get_model(write_config)

        # The exact error propagates unwrapped (ADR-094 controlled inversion).
        assert exc_info.value.user_id == user
        assert exc_info.value.month_spend_usd == 12.5
        assert exc_info.value.monthly_budget_usd == 10.0
        assert guard.checked == [user]
        assert provider_calls == []

    async def test_no_guard_set_returns_model_normally(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
        test_model: TestModel,
    ) -> None:
        """No guard armed => user attribution present but get_model unaffected."""
        _set_user()

        model = await registry_with_test_model.get_model(write_config)

        assert model is test_model

    async def test_none_user_is_noop_even_with_raising_guard(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
        test_model: TestModel,
    ) -> None:
        """usage_user_id unset => the guard is never consulted (tests/CLI path)."""
        guard = _arm_over_budget_guard()

        model = await registry_with_test_model.get_model(write_config)

        assert model is test_model
        assert guard.checked == []


class TestBothPopulationsInheritGate:
    """One gate, two path tests — the raise surfaces through each population."""

    async def test_run_registry_path_surfaces_budget_exceeded_error(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """registry.run() (registry_run.py population) surfaces the gate raise."""
        guard = _arm_over_budget_guard()
        user = _set_user()

        with pytest.raises(BudgetExceededError) as exc_info:
            await registry_with_test_model.run(
                LLMIntent.NAME_GENERATE,
                prompt="x",
                config=write_config,
            )

        assert exc_info.value.user_id == user
        assert guard.checked == [user]

    async def test_prepare_capability_path_surfaces_budget_exceeded_error(
        self,
        registry: ModelRegistry,
        write_config: ResolvedModelConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """prepare() (capability population) surfaces the raise pre-provider."""
        provider_calls = _patch_provider_sentinel(monkeypatch)
        _arm_over_budget_guard()
        user = _set_user()

        with pytest.raises(BudgetExceededError) as exc_info:
            await registry.prepare(write_config)

        assert exc_info.value.user_id == user
        assert provider_calls == []
