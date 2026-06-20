"""CR-08 P1 model-limit calibration status tests."""

from __future__ import annotations

from narrare_core.llm.model_calibration import (
    ModelLimitCalibrationStatus,
    ModelLimitMetadataSnapshot,
    calibrate_model_limits,
)


def test_calibration_known_fresh_carries_provider_output_cap() -> None:
    result = calibrate_model_limits(
        provider="openai",
        model_id="gpt-test",
        snapshot=ModelLimitMetadataSnapshot(
            data={"models": {"gpt-test": {"limit": {"context": 128000, "output": 4096}}}},
            source="models.dev",
            source_timestamp=123.0,
            age_seconds=4.0,
        ),
    )

    assert result.status is ModelLimitCalibrationStatus.KNOWN_FRESH
    assert result.provider_max_output_tokens == 4096
    assert result.context_window_tokens == 128000
    assert result.source == "models.dev"
    assert result.source_timestamp == 123.0


def test_calibration_known_stale_marks_stale_metadata() -> None:
    result = calibrate_model_limits(
        provider="anthropic",
        model_id="claude-test",
        snapshot=ModelLimitMetadataSnapshot(
            data={"models": {"claude-test": {"limit": {"context": 200000, "output": 8192}}}},
            source="cache",
            is_stale=True,
            age_seconds=90000.0,
            error="remote unavailable",
        ),
    )

    assert result.status is ModelLimitCalibrationStatus.KNOWN_STALE
    assert result.provider_max_output_tokens == 8192
    assert result.cache_age_seconds == 90000.0
    assert result.detail == "remote unavailable"


def test_calibration_unknown_model_when_source_available_without_model() -> None:
    result = calibrate_model_limits(
        provider="openai",
        model_id="missing-model",
        snapshot=ModelLimitMetadataSnapshot(data={"models": {}}, source="models.dev"),
    )

    assert result.status is ModelLimitCalibrationStatus.UNKNOWN_MODEL
    assert result.provider_max_output_tokens is None


def test_calibration_offline_no_cache_when_no_metadata_available() -> None:
    result = calibrate_model_limits(
        provider="openai",
        model_id="gpt-test",
        snapshot=ModelLimitMetadataSnapshot(data=None, source="models.dev", error="timeout"),
    )

    assert result.status is ModelLimitCalibrationStatus.OFFLINE_NO_CACHE
    assert result.provider_max_output_tokens is None
    assert result.detail == "timeout"


def test_calibration_invalid_metadata_when_limits_are_malformed() -> None:
    result = calibrate_model_limits(
        provider="openai",
        model_id="gpt-test",
        snapshot=ModelLimitMetadataSnapshot(
            data={"models": {"gpt-test": {"limit": {"context": 128000, "output": "many"}}}},
            source="cache",
        ),
    )

    assert result.status is ModelLimitCalibrationStatus.INVALID_METADATA
    assert result.provider_max_output_tokens is None
