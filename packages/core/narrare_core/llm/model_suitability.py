"""CR-08 P1 model suitability evaluation policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from narrare_core.llm.intent_profiles import get_intent_profile
from narrare_core.llm.model_calibration import ModelLimitCalibration, ModelLimitCalibrationStatus
from narrare_core.llm.token_profiles import (
    PROFILE_OUTPUT_LIMITS,
    TOKEN_PROFILE_MINIMUM_OUTPUT_FLOORS,
)

if TYPE_CHECKING:
    from narrare_core.llm.intents import LLMIntent


class SuitabilitySeverity(StrEnum):
    """CR-08 suitability severity boundaries."""

    ADVISORY = "advisory"
    WARNING = "warning"
    HARD_BLOCK = "hard_block"


@dataclass(frozen=True, slots=True)
class ModelSuitabilityIssue:
    """One suitability finding for a model/intent invocation."""

    severity: SuitabilitySeverity
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ModelSuitabilityResult:
    """Suitability decision for one model/intent/output request."""

    intent: LLMIntent
    output_profile: str
    requested_output_tokens: int
    effective_output_tokens: int
    recommended_output_tokens: int
    minimum_viable_output_tokens: int
    calibration_status: ModelLimitCalibrationStatus
    provider_max_output_tokens: int | None
    severity: SuitabilitySeverity
    issues: tuple[ModelSuitabilityIssue, ...]

    @property
    def is_allowed(self) -> bool:
        """Return whether the model call may proceed."""

        return self.severity is not SuitabilitySeverity.HARD_BLOCK


_CAPABILITY_RANK: dict[str, int] = {
    "fast": 1,
    "balanced": 2,
    "creative": 3,
    "reasoning": 3,
}


def evaluate_model_suitability(
    *,
    intent: LLMIntent,
    calibration: ModelLimitCalibration,
    requested_output_tokens: int,
    effective_output_tokens: int | None = None,
    model_capability_tier: str | None = None,
    required_input_tokens: int | None = None,
) -> ModelSuitabilityResult:
    """Evaluate CR-08 P1 suitability for a model invocation.

    Unknown model capability is never a hard block. Hard blocks are limited to
    known impossible/unsafe calls such as provider caps below the minimum viable
    output floor or a known context window that cannot fit required input plus
    the minimum output floor.
    """

    intent_profile = get_intent_profile(intent)
    output_profile = intent_profile.output_profile
    minimum_floor = TOKEN_PROFILE_MINIMUM_OUTPUT_FLOORS[output_profile]
    recommended_output = PROFILE_OUTPUT_LIMITS[output_profile]
    effective = (
        effective_output_tokens if effective_output_tokens is not None else requested_output_tokens
    )

    issues: list[ModelSuitabilityIssue] = []
    _add_calibration_issue(issues, calibration.status)
    _add_provider_cap_issue(
        issues,
        provider_max=calibration.provider_max_output_tokens,
        requested_output_tokens=requested_output_tokens,
        minimum_floor=minimum_floor,
    )
    _add_context_issue(
        issues,
        context_window=calibration.context_window_tokens,
        required_input_tokens=required_input_tokens,
        minimum_floor=minimum_floor,
    )
    _add_capability_issue(
        issues,
        recommended_tier=intent_profile.capability_tier,
        actual_tier=model_capability_tier,
    )

    severity = _max_severity(issues)
    return ModelSuitabilityResult(
        intent=intent,
        output_profile=output_profile,
        requested_output_tokens=requested_output_tokens,
        effective_output_tokens=effective,
        recommended_output_tokens=recommended_output,
        minimum_viable_output_tokens=minimum_floor,
        calibration_status=calibration.status,
        provider_max_output_tokens=calibration.provider_max_output_tokens,
        severity=severity,
        issues=tuple(issues),
    )


def _add_calibration_issue(
    issues: list[ModelSuitabilityIssue],
    status: ModelLimitCalibrationStatus,
) -> None:
    if status is ModelLimitCalibrationStatus.KNOWN_FRESH:
        return
    issues.append(
        ModelSuitabilityIssue(
            severity=SuitabilitySeverity.WARNING,
            code=f"calibration_{status.value}",
            message=f"Model limit calibration status is {status.value}.",
        )
    )


def _add_provider_cap_issue(
    issues: list[ModelSuitabilityIssue],
    *,
    provider_max: int | None,
    requested_output_tokens: int,
    minimum_floor: int,
) -> None:
    if provider_max is None:
        return
    if provider_max < minimum_floor:
        issues.append(
            ModelSuitabilityIssue(
                severity=SuitabilitySeverity.HARD_BLOCK,
                code="provider_cap_below_minimum_floor",
                message="Known provider output cap is below the intent minimum viable floor.",
            )
        )
        return
    if provider_max < requested_output_tokens:
        issues.append(
            ModelSuitabilityIssue(
                severity=SuitabilitySeverity.WARNING,
                code="provider_cap_below_requested",
                message="Requested output exceeds known provider output cap and will be capped.",
            )
        )


def _add_context_issue(
    issues: list[ModelSuitabilityIssue],
    *,
    context_window: int | None,
    required_input_tokens: int | None,
    minimum_floor: int,
) -> None:
    if context_window is None or required_input_tokens is None:
        return
    if required_input_tokens + minimum_floor > context_window:
        issues.append(
            ModelSuitabilityIssue(
                severity=SuitabilitySeverity.HARD_BLOCK,
                code="context_window_below_required_floor",
                message="Known context window cannot fit required input plus minimum output.",
            )
        )


def _add_capability_issue(
    issues: list[ModelSuitabilityIssue],
    *,
    recommended_tier: str,
    actual_tier: str | None,
) -> None:
    if actual_tier is None:
        issues.append(
            ModelSuitabilityIssue(
                severity=SuitabilitySeverity.ADVISORY,
                code="capability_unknown",
                message="Model capability tier is unknown for this intent.",
            )
        )
        return
    if _CAPABILITY_RANK.get(actual_tier, 0) < _CAPABILITY_RANK.get(recommended_tier, 0):
        issues.append(
            ModelSuitabilityIssue(
                severity=SuitabilitySeverity.ADVISORY,
                code="capability_below_recommendation",
                message="Model capability tier is below the intent recommendation.",
            )
        )


def _max_severity(issues: list[ModelSuitabilityIssue]) -> SuitabilitySeverity:
    if any(issue.severity is SuitabilitySeverity.HARD_BLOCK for issue in issues):
        return SuitabilitySeverity.HARD_BLOCK
    if any(issue.severity is SuitabilitySeverity.WARNING for issue in issues):
        return SuitabilitySeverity.WARNING
    return SuitabilitySeverity.ADVISORY
