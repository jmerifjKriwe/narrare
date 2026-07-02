"""CR-08 P1 model suitability policy tests."""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_calibration import ModelLimitCalibration, ModelLimitCalibrationStatus
from narrare_core.llm.model_suitability import SuitabilitySeverity, evaluate_model_suitability


def _calibration(
    status: ModelLimitCalibrationStatus,
    *,
    output: int | None = None,
    context: int | None = None,
) -> ModelLimitCalibration:
    return ModelLimitCalibration(
        provider="test",
        model_id="test-model",
        status=status,
        provider_max_output_tokens=output,
        context_window_tokens=context,
        source="test",
    )


def test_known_low_cap_above_floor_warns_and_caps_effective_output() -> None:
    result = evaluate_model_suitability(
        intent=LLMIntent.WRITE,
        calibration=_calibration(ModelLimitCalibrationStatus.KNOWN_FRESH, output=4096),
        requested_output_tokens=8000,
        effective_output_tokens=4096,
        model_capability_tier="creative",
    )

    assert result.severity is SuitabilitySeverity.WARNING
    assert result.minimum_viable_output_tokens == 2048
    assert result.effective_output_tokens == 4096
    assert any(issue.code == "provider_cap_below_requested" for issue in result.issues)


def test_provider_cap_below_minimum_floor_hard_blocks() -> None:
    result = evaluate_model_suitability(
        intent=LLMIntent.CONSISTENCY,
        calibration=_calibration(ModelLimitCalibrationStatus.KNOWN_FRESH, output=2048),
        requested_output_tokens=16000,
        effective_output_tokens=2048,
        model_capability_tier="reasoning",
    )

    assert result.severity is SuitabilitySeverity.HARD_BLOCK
    assert result.is_allowed is False
    assert any(issue.code == "provider_cap_below_minimum_floor" for issue in result.issues)


def test_known_context_window_below_required_floor_hard_blocks() -> None:
    """Required input + minimum floor exceeding a known context window hard-blocks."""
    result = evaluate_model_suitability(
        intent=LLMIntent.WRITE,
        calibration=_calibration(
            ModelLimitCalibrationStatus.KNOWN_FRESH, output=8192, context=4096
        ),
        requested_output_tokens=8192,
        effective_output_tokens=8192,
        model_capability_tier="creative",
        required_input_tokens=8192,  # 8192 + WRITE minimum floor > 4096 context
    )

    assert result.severity is SuitabilitySeverity.HARD_BLOCK
    assert result.is_allowed is False
    assert any(issue.code == "context_window_below_required_floor" for issue in result.issues)


def test_unknown_model_is_warning_not_hard_block() -> None:
    result = evaluate_model_suitability(
        intent=LLMIntent.WRITE,
        calibration=_calibration(ModelLimitCalibrationStatus.UNKNOWN_MODEL),
        requested_output_tokens=8000,
        effective_output_tokens=8000,
        model_capability_tier=None,
    )

    assert result.severity is SuitabilitySeverity.WARNING
    assert result.is_allowed is True
    assert any(issue.code == "calibration_unknown_model" for issue in result.issues)


def test_offline_no_cache_is_warning_not_hard_block() -> None:
    result = evaluate_model_suitability(
        intent=LLMIntent.CHAT,
        calibration=_calibration(ModelLimitCalibrationStatus.OFFLINE_NO_CACHE),
        requested_output_tokens=2000,
        effective_output_tokens=2000,
        model_capability_tier="balanced",
    )

    assert result.severity is SuitabilitySeverity.WARNING
    assert result.is_allowed is True
    assert any(issue.code == "calibration_offline_no_cache" for issue in result.issues)


def test_stale_metadata_is_warning() -> None:
    result = evaluate_model_suitability(
        intent=LLMIntent.CHAT,
        calibration=_calibration(ModelLimitCalibrationStatus.KNOWN_STALE, output=2000),
        requested_output_tokens=2000,
        effective_output_tokens=2000,
        model_capability_tier="balanced",
    )

    assert result.severity is SuitabilitySeverity.WARNING
    assert any(issue.code == "calibration_known_stale" for issue in result.issues)


def test_capability_below_recommendation_is_advisory() -> None:
    result = evaluate_model_suitability(
        intent=LLMIntent.WRITE,
        calibration=_calibration(ModelLimitCalibrationStatus.KNOWN_FRESH, output=16000),
        requested_output_tokens=8000,
        effective_output_tokens=8000,
        model_capability_tier="fast",
    )

    assert result.severity is SuitabilitySeverity.ADVISORY
    assert result.is_allowed is True
    assert any(issue.code == "capability_below_recommendation" for issue in result.issues)


def test_unknown_capability_with_known_metadata_is_advisory_only() -> None:
    result = evaluate_model_suitability(
        intent=LLMIntent.SUGGEST,
        calibration=_calibration(ModelLimitCalibrationStatus.KNOWN_FRESH, output=500),
        requested_output_tokens=500,
        effective_output_tokens=500,
        model_capability_tier=None,
    )

    assert result.severity is SuitabilitySeverity.ADVISORY
    assert result.is_allowed is True
    assert any(issue.code == "capability_unknown" for issue in result.issues)
