"""Token-limit metadata service — catalogue + calibration + suitability.

CR-08 P1 read-only public boundary. Exposes:

* the Core-derived profile catalogue and caps (D1/D4),
* typed provider/model calibration evidence (D5), and
* model suitability evaluation with advisory/warning/hard-block severities (D6).

The service is stateless apart from the injected ``calibration_provider``,
which defaults to Core's :func:`~narrare_core.llm.cost_rates.get_model_limit_calibration`.
Tests inject a deterministic provider so no network is required.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from narrare.settings.token_limits.schemas import (
    CalibrationSourceMetadata,
    SuitabilityIssueMetadata,
    SuitabilityMetadata,
    TokenLimitsCatalog,
    build_catalog,
)
from narrare_core.llm.cost_rates import get_model_limit_calibration
from narrare_core.llm.model_calibration import ModelLimitCalibration
from narrare_core.llm.model_suitability import (
    ModelSuitabilityResult,
    evaluate_model_suitability,
)

if TYPE_CHECKING:
    from narrare_core.llm.intents import LLMIntent

#: Type of the injectable calibration collaborator.
CalibrationProvider = Callable[[str, str], ModelLimitCalibration]


class TokenLimitsMetadataService:
    """Public boundary for token-limit catalogue and model evaluation metadata.

    Args:
        calibration_provider: Callable ``(provider, model_id) -> ModelLimitCalibration``.
            Defaults to Core's models.dev-backed resolver. Inject a fake in
            tests for deterministic offline/unknown/provider-too-small cases.
    """

    def __init__(
        self,
        calibration_provider: CalibrationProvider = get_model_limit_calibration,
    ) -> None:
        self._calibration_provider = calibration_provider

    def get_catalogue(self) -> TokenLimitsCatalog:
        """Return the Core-derived profile catalogue and caps."""

        return build_catalog()

    def get_calibration(self, provider: str, model_id: str) -> CalibrationSourceMetadata:
        """Resolve typed calibration evidence for a provider/model pair."""

        calibration = self._calibration_provider(provider, model_id)
        return _calibration_to_metadata(calibration)

    def evaluate_suitability(
        self,
        *,
        provider: str,
        model_id: str,
        intent: LLMIntent,
        requested_output_tokens: int,
        model_capability_tier: str | None = None,
        required_input_tokens: int | None = None,
    ) -> SuitabilityMetadata:
        """Evaluate CR-08 P1 suitability for a model invocation.

        Args:
            provider: Provider name (e.g. "openai").
            model_id: Model identifier (e.g. "gpt-4o").
            intent: The invocation intent driving the output profile/floor.
            requested_output_tokens: Requested output budget for the call.
            model_capability_tier: Optional declared capability tier.
            required_input_tokens: Optional required input budget, used for
                context-window hard-block detection.

        Returns:
            Typed suitability metadata with severity, issues, and the
            underlying calibration status.
        """

        calibration = self._calibration_provider(provider, model_id)
        result = evaluate_model_suitability(
            intent=intent,
            calibration=calibration,
            requested_output_tokens=requested_output_tokens,
            model_capability_tier=model_capability_tier,
            required_input_tokens=required_input_tokens,
        )
        return _suitability_to_metadata(result)


# ---------------------------------------------------------------------------
# Core -> schema mappers
# ---------------------------------------------------------------------------


def _calibration_to_metadata(c: ModelLimitCalibration) -> CalibrationSourceMetadata:
    """Map a Core calibration result to the API metadata schema."""

    return CalibrationSourceMetadata(
        provider=c.provider,
        model_id=c.model_id,
        status=c.status.value,
        source=c.source,
        provider_max_output_tokens=c.provider_max_output_tokens,
        context_window_tokens=c.context_window_tokens,
        source_timestamp=c.source_timestamp,
        cache_age_seconds=c.cache_age_seconds,
        detail=c.detail,
    )


def _suitability_to_metadata(r: ModelSuitabilityResult) -> SuitabilityMetadata:
    """Map a Core suitability result to the API metadata schema."""

    return SuitabilityMetadata(
        intent=r.intent.value,
        output_profile=r.output_profile,
        requested_output_tokens=r.requested_output_tokens,
        effective_output_tokens=r.effective_output_tokens,
        recommended_output_tokens=r.recommended_output_tokens,
        minimum_viable_output_tokens=r.minimum_viable_output_tokens,
        calibration_status=r.calibration_status.value,
        provider_max_output_tokens=r.provider_max_output_tokens,
        severity=r.severity.value,
        is_allowed=r.is_allowed,
        issues=[
            SuitabilityIssueMetadata(
                severity=issue.severity.value,
                code=issue.code,
                message=issue.message,
            )
            for issue in r.issues
        ],
    )
