"""Dependency-injection factories and response-shaping helpers for the
token-limits router.

Kept in a dedicated module so ``router.py`` stays a thin route-declaration
file under the RULE-04 size limit. Everything here is router-layer wiring
(DI factories and HTTP response shaping); no business logic (RULE-06).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status

from narrare._app.config import get_settings
from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.settings.token_limits.repository import (
    ProjectTokenLimitsRepository,
    UserTokenLimitsRepository,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare._app.config import Settings
    from narrare.settings.token_limits.metadata_service import (
        TokenLimitsMetadataService,
    )
    from narrare.settings.token_limits.schemas import (
        CalibrationSourceMetadata,
        SuitabilityMetadata,
    )
    from narrare.settings.token_limits.service import TokenLimitsService


def get_token_limits_service(
    session: SessionDep,
    config: Settings = Depends(get_settings),  # noqa: B008 — FastAPI DI pattern
) -> TokenLimitsService:
    """Factory for TokenLimitsService with DB-backed repositories."""

    from narrare.settings.token_limits.service import TokenLimitsService

    return TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=config,
    )


def get_token_limits_metadata_service() -> TokenLimitsMetadataService:
    """Factory for the stateless metadata service (CR-08 P1 catalogue)."""

    from narrare.settings.token_limits.metadata_service import (
        TokenLimitsMetadataService,
    )

    return TokenLimitsMetadataService()


def resolve_model_metadata(
    metadata_service: TokenLimitsMetadataService,
    *,
    provider: str | None,
    model_id: str | None,
    intent: str | None,
    requested_output_tokens: int,
) -> tuple[CalibrationSourceMetadata | None, SuitabilityMetadata | None]:
    """Attach optional calibration/suitability metadata to the response.

    ``intent`` requires ``provider`` and ``model_id``; an invalid intent
    string yields HTTP 422. Returns ``(None, None)`` when no provider/model
    is supplied.
    """
    if provider is None or model_id is None:
        return None, None
    calibration = metadata_service.get_calibration(provider, model_id)
    if intent is None:
        return calibration, None
    try:
        resolved_intent = LLMIntent(intent)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown intent: {intent}",
        ) from exc
    suitability = metadata_service.evaluate_suitability(
        provider=provider,
        model_id=model_id,
        intent=resolved_intent,
        requested_output_tokens=requested_output_tokens,
    )
    return calibration, suitability


# Re-exported so route handlers can declare the auth dependency concisely.
__all__ = ["CurrentUserIdDep", "resolve_model_metadata"]
