"""Budget settings API surface — schemas, service, invalidation slot (STATS-002, ADR-094).

Binding spec A-7: get/set ``monthly_budget_usd`` (nullable Decimal ≥ 0;
negative/garbage ⇒ 422) + ``budget_mode`` ∈ {'warn','block'} through the
existing single ``PATCH /ai`` settings endpoint; NULL budget = unset;
write-through cache invalidation hook so the A5 guard's config cache
stays consistent (ADR-093 D2 slot pattern).

FastAPI maps the pydantic ``ValidationError``s pinned here to HTTP 422
(standard ``RequestValidationError`` handling) — asserted at schema level,
the lowest level where the contract lives.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from narrare.analytics.budget_invalidation import set_budget_config_invalidator
from narrare.settings.schemas import (
    UpdateUserAiSettingsRequest,
    UserAiSettingsResponse,
)
from narrare.settings.user_ai_settings_service import UserAiSettingsService

# ---------------------------------------------------------------------------
# Fakes (mirror tests/unit/settings/test_user_ai_settings_service.py)
# ---------------------------------------------------------------------------


@dataclass
class FakeUserAiSettings:
    user_id: uuid.UUID
    default_provider_id: uuid.UUID | None = None
    default_model: str = ""
    category_overrides: dict[str, Any] = field(default_factory=dict)
    intent_overrides: dict[str, Any] = field(default_factory=dict)
    embedding_provider: str = "auto"
    embedding_model: str | None = None
    monthly_budget_usd: Decimal | None = None
    budget_mode: str = "warn"
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def provider_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_ai_settings_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_providers_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def service(
    mock_ai_settings_repo: AsyncMock,
    mock_providers_repo: AsyncMock,
) -> UserAiSettingsService:
    return UserAiSettingsService(
        ai_settings_repo=mock_ai_settings_repo,
        providers_repo=mock_providers_repo,
    )


@pytest.fixture
def invalidation_calls() -> Iterator[list[uuid.UUID]]:
    """Register a recording invalidator; always reset the slot afterwards."""
    calls: list[uuid.UUID] = []
    set_budget_config_invalidator(calls.append)
    yield calls
    set_budget_config_invalidator(None)


# ======================================================================
# Response schema (read surface)
# ======================================================================


class TestBudgetResponseSchema:
    def test_budget_fields_default_to_unset(self) -> None:
        resp = UserAiSettingsResponse(
            user_id=uuid.uuid4(),
            default_provider_id=None,
            default_model="",
            category_overrides={},
            intent_overrides={},
            updated_at=datetime.now(UTC),
        )
        assert resp.monthly_budget_usd is None, "NULL = no budget (gate no-op)"
        assert resp.budget_mode == "warn", "default mode mirrors column default"

    def test_budget_fields_round_trip(self) -> None:
        resp = UserAiSettingsResponse(
            user_id=uuid.uuid4(),
            default_provider_id=None,
            default_model="",
            category_overrides={},
            intent_overrides={},
            monthly_budget_usd=Decimal("25.00"),
            budget_mode="block",
            updated_at=datetime.now(UTC),
        )
        assert resp.monthly_budget_usd == Decimal("25.00")
        assert resp.budget_mode == "block"

    def test_response_reads_budget_from_orm_object(self) -> None:
        settings = FakeUserAiSettings(
            user_id=uuid.uuid4(),
            monthly_budget_usd=Decimal("10.50"),
            budget_mode="warn",
        )
        resp = UserAiSettingsResponse.model_validate(settings)
        assert resp.monthly_budget_usd == Decimal("10.50")
        assert resp.budget_mode == "warn"


# ======================================================================
# Request schema (write surface — FastAPI maps these to 422)
# ======================================================================


class TestBudgetRequestValidation:
    def test_budget_fields_default_to_not_provided(self) -> None:
        req = UpdateUserAiSettingsRequest()
        assert req.monthly_budget_usd is None
        assert req.budget_mode is None
        assert "monthly_budget_usd" not in req.model_fields_set
        assert "budget_mode" not in req.model_fields_set

    def test_explicit_null_budget_is_a_provided_field(self) -> None:
        """NULL budget = unset — explicit null must be distinguishable
        from "not provided" (the exclude_none conflation is handled in
        the service via model_fields_set)."""
        req = UpdateUserAiSettingsRequest(monthly_budget_usd=None)
        assert "monthly_budget_usd" in req.model_fields_set
        assert req.monthly_budget_usd is None

    @pytest.mark.parametrize("value", ["warn", "block"])
    def test_budget_mode_accepts_enum_values(self, value: Literal["warn", "block"]) -> None:
        req = UpdateUserAiSettingsRequest(budget_mode=value)
        assert req.budget_mode == value

    def test_zero_budget_is_valid(self) -> None:
        req = UpdateUserAiSettingsRequest(monthly_budget_usd=Decimal("0.00"))
        assert req.monthly_budget_usd == Decimal("0.00")

    def test_max_column_precision_is_valid(self) -> None:
        """NUMERIC(10,2) ceiling: 99 999 999.99."""
        req = UpdateUserAiSettingsRequest(monthly_budget_usd=Decimal("99999999.99"))
        assert req.monthly_budget_usd == Decimal("99999999.99")

    @pytest.mark.parametrize("value", [-1, "-5", "-0.01", Decimal("-1.00")])
    def test_negative_budget_is_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError):
            UpdateUserAiSettingsRequest.model_validate({"monthly_budget_usd": value})

    @pytest.mark.parametrize("value", ["abc", "", "12,50", "NaN", float("nan")])
    def test_garbage_budget_is_rejected(self, value: object) -> None:
        """Garbage (unparseable / non-finite) ⇒ 422. Explicit ``None`` is
        NOT garbage — it is the valid unset (covered above)."""
        with pytest.raises(ValidationError):
            UpdateUserAiSettingsRequest.model_validate({"monthly_budget_usd": value})

    def test_more_than_two_decimal_places_is_rejected(self) -> None:
        """Mirrors NUMERIC(10,2) — silent rounding would diverge from the
        stored value; reject instead."""
        with pytest.raises(ValidationError):
            UpdateUserAiSettingsRequest(monthly_budget_usd=Decimal("10.123"))

    def test_column_overflow_is_rejected(self) -> None:
        """NUMERIC(10,2) overflow would surface as a DB DataError (500);
        the schema rejects it up front (422)."""
        with pytest.raises(ValidationError):
            UpdateUserAiSettingsRequest(monthly_budget_usd=Decimal("100000000"))

    @pytest.mark.parametrize("value", ["enforce", "WARN", "", "hard_stop", None])
    def test_invalid_budget_mode_is_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError):
            UpdateUserAiSettingsRequest.model_validate({"budget_mode": value})

    def test_explicit_null_budget_mode_is_rejected_but_omission_stays_valid(self) -> None:
        """Regression (fix round 1): ``PATCH /ai`` with ``{"budget_mode":
        null``} must 422 at the schema — "unset" is meaningless for
        budget_mode (NOT NULL column; only ``monthly_budget_usd`` is
        nullable), and letting it through reaches the DB as an
        IntegrityError (500). Omitting the field stays valid: pydantic
        skips field validators for not-provided defaults, so the
        validator only sees an explicit ``null`` payload."""
        with pytest.raises(ValidationError):
            UpdateUserAiSettingsRequest.model_validate({"budget_mode": None})
        omitted = UpdateUserAiSettingsRequest()
        assert "budget_mode" not in omitted.model_fields_set
        assert omitted.budget_mode is None


# ======================================================================
# Service write surface (PATCH /ai delegation)
# ======================================================================


class TestBudgetServiceWrite:
    async def test_write_budget_value_reaches_repository(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
        invalidation_calls: list[uuid.UUID],
    ) -> None:
        updated = FakeUserAiSettings(user_id=user_id, monthly_budget_usd=Decimal("25.00"))
        mock_ai_settings_repo.get = AsyncMock(return_value=updated)
        mock_ai_settings_repo.update = AsyncMock(return_value=updated)

        result = await service.update_settings(
            user_id, UpdateUserAiSettingsRequest(monthly_budget_usd=Decimal("25.00"))
        )

        assert result.monthly_budget_usd == Decimal("25.00")
        _, kwargs = mock_ai_settings_repo.update.call_args
        assert kwargs["monthly_budget_usd"] == Decimal("25.00")

    async def test_write_budget_triggers_invalidation(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
        invalidation_calls: list[uuid.UUID],
    ) -> None:
        updated = FakeUserAiSettings(user_id=user_id)
        mock_ai_settings_repo.get = AsyncMock(return_value=updated)
        mock_ai_settings_repo.update = AsyncMock(return_value=updated)

        await service.update_settings(
            user_id, UpdateUserAiSettingsRequest(monthly_budget_usd=Decimal("5.00"))
        )

        assert invalidation_calls == [user_id], "write-through cache invalidation (A-7)"

    async def test_explicit_null_budget_unsets_and_invalidates(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
        invalidation_calls: list[uuid.UUID],
    ) -> None:
        updated = FakeUserAiSettings(user_id=user_id, monthly_budget_usd=None)
        mock_ai_settings_repo.get = AsyncMock(return_value=updated)
        mock_ai_settings_repo.update = AsyncMock(return_value=updated)

        result = await service.update_settings(
            user_id, UpdateUserAiSettingsRequest(monthly_budget_usd=None)
        )

        _, kwargs = mock_ai_settings_repo.update.call_args
        assert kwargs["monthly_budget_usd"] is None, "NULL budget = unset"
        assert result.monthly_budget_usd is None
        assert invalidation_calls == [user_id]

    async def test_write_budget_mode_triggers_invalidation(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
        invalidation_calls: list[uuid.UUID],
    ) -> None:
        updated = FakeUserAiSettings(user_id=user_id, budget_mode="block")
        mock_ai_settings_repo.get = AsyncMock(return_value=updated)
        mock_ai_settings_repo.update = AsyncMock(return_value=updated)

        result = await service.update_settings(
            user_id, UpdateUserAiSettingsRequest(budget_mode="block")
        )

        assert result.budget_mode == "block"
        assert invalidation_calls == [user_id]

    async def test_budget_mode_transition_warn_block_warn_invalidates_per_write(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
        invalidation_calls: list[uuid.UUID],
    ) -> None:
        """warn → block → warn: each write stores the requested mode and
        fires the write-through invalidation exactly once per write."""
        mock_ai_settings_repo.get = AsyncMock()
        mock_ai_settings_repo.update = AsyncMock()
        modes: tuple[Literal["warn", "block"], ...] = ("warn", "block", "warn")

        for mode in modes:
            mock_ai_settings_repo.update.return_value = FakeUserAiSettings(
                user_id=user_id, budget_mode=mode
            )

            result = await service.update_settings(
                user_id, UpdateUserAiSettingsRequest(budget_mode=mode)
            )

            assert result.budget_mode == mode, f"stored value after writing {mode!r}"
            _, kwargs = mock_ai_settings_repo.update.call_args
            assert kwargs["budget_mode"] == mode

        assert invalidation_calls == [user_id, user_id, user_id], "one invalidation per write"

    async def test_non_budget_write_does_not_invalidate(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        mock_providers_repo: AsyncMock,
        user_id: uuid.UUID,
        provider_id: uuid.UUID,
        invalidation_calls: list[uuid.UUID],
    ) -> None:
        """Only budget-config writes touch the guard's cache."""
        provider = AsyncMock()
        provider.user_id = user_id
        provider.is_active = True
        mock_providers_repo.get = AsyncMock(return_value=provider)

        updated = FakeUserAiSettings(user_id=user_id)
        mock_ai_settings_repo.get = AsyncMock(return_value=updated)
        mock_ai_settings_repo.update = AsyncMock(return_value=updated)

        await service.update_settings(
            user_id,
            UpdateUserAiSettingsRequest(
                default_provider_id=provider_id,
                default_model="claude-sonnet-4-5",
            ),
        )

        assert invalidation_calls == []

    async def test_get_settings_exposes_budget_fields(
        self,
        service: UserAiSettingsService,
        mock_ai_settings_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        settings = FakeUserAiSettings(
            user_id=user_id,
            monthly_budget_usd=Decimal("42.00"),
            budget_mode="block",
        )
        mock_ai_settings_repo.get = AsyncMock(return_value=settings)

        result = await service.get_settings(user_id)

        assert result.monthly_budget_usd == Decimal("42.00")
        assert result.budget_mode == "block"
