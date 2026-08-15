"""CR-08 P2 tests for consistency caps and false-control removal.

Verifies:
1. ``max_selection_words`` is NOT present in the API response schema
   (removed false control — CR-AUFG-08-05).
2. The ``NARRARE_DEFAULT_MAX_SELECTION_WORDS`` env override still
   affects resolved limits through the internal merge path.
"""

from __future__ import annotations

from dataclasses import dataclass

from narrare.settings.token_limits.schemas import TokenLimitOverridesResponse
from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
)

# ======================================================================
# Test 1: max_selection_words absent from API response
# ======================================================================


def test_max_selection_words_not_in_api_response() -> None:
    """max_selection_words must NOT appear in TokenLimitOverridesResponse.

    CR-AUFG-08-05: removed false control. The field is internal only
    (contract type + validators) and must not leak into the GET response.
    """
    fields = set(TokenLimitOverridesResponse.model_fields.keys())
    assert "max_selection_words" not in fields, (
        "max_selection_words leaked into API response — remove it from TokenLimitOverridesResponse"
    )


def test_api_response_serializes_without_max_selection_words() -> None:
    """Serializing a TokenLimitOverridesResponse must NOT produce
    a max_selection_words key in the resulting JSON/dict.
    """
    from narrare.settings.token_limits.schemas import build_catalog

    response = TokenLimitOverridesResponse(
        output_limit=4096,
        token_profile="balanced",
        effective_output_limit=2000,
        metadata=build_catalog(),
    )
    data = response.model_dump(exclude_none=True)
    assert "max_selection_words" not in data, (
        f"max_selection_words found in serialized response: {data}"
    )


# ======================================================================
# Test 2: env override still affects resolved limits
# ======================================================================


async def test_env_override_affects_resolved_limits_via_internal_merge() -> None:
    """Simulating NARRARE_DEFAULT_MAX_SELECTION_WORDS via config must
    propagate into the resolved TokenLimitOverrides contract type.

    This test proves the env override path is NOT removed — only the
    API response field is removed.
    """
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare.settings.token_limits.service import TokenLimitsService

    # --- fakes ---

    @dataclass
    class _FakeConfig:
        default_max_tokens: int = 4096
        ws_idle_timeout_seconds: int = 1800
        consistency_max_chapter_tokens: int = 2000
        consistency_max_kb_entries: int = 100
        default_max_selection_words: int = 5000  # <-- overridden
        context_total_budget: int = DEFAULT_TOTAL_BUDGET
        series_history_budget: int = DEFAULT_SERIES_HISTORY_BUDGET

    class _FakeRepo:
        """Minimal repo that returns no overrides."""

        async def get(self, pk: str) -> None:  # type: ignore[arg-type,override]
            return None

        async def update(self, pk: str, overrides: dict[str, object]) -> None:
            pass

    service = TokenLimitsService(
        user_repo=_FakeRepo(),  # type: ignore[arg-type]
        project_repo=_FakeRepo(),  # type: ignore[arg-type]
        config=_FakeConfig(),  # type: ignore[arg-type]
    )
    resolved = await service.get_resolved_limits(user_id="test-user")

    assert isinstance(resolved, TokenLimitOverrides)
    assert resolved.max_selection_words == 5000, (
        f"Expected max_selection_words=5000 from env, got {resolved.max_selection_words}"
    )


def test_env_default_max_selection_words_default_is_2000() -> None:
    """The code-default value for max_selection_words must be 2000."""
    from narrare.settings.token_limits.contracts import TokenLimitOverrides

    defaults = TokenLimitOverrides()
    assert defaults.max_selection_words == 2000
