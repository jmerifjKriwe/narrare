"""Typed model-limit calibration results for CR-08 P1."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast


class ModelLimitCalibrationStatus(StrEnum):
    """Evidence status for provider/model output-limit metadata."""

    KNOWN_FRESH = "known_fresh"
    KNOWN_STALE = "known_stale"
    UNKNOWN_MODEL = "unknown_model"
    OFFLINE_NO_CACHE = "offline_no_cache"
    INVALID_METADATA = "invalid_metadata"


@dataclass(frozen=True, slots=True)
class ModelLimits:
    """Model token limits from provider metadata."""

    context: int
    """Maximum context window size in tokens."""
    output: int
    """Maximum output tokens allowed."""


@dataclass(frozen=True, slots=True)
class ModelLimitMetadataSnapshot:
    """Raw model metadata plus source/freshness evidence."""

    data: Mapping[str, object] | None
    source: str
    is_stale: bool = False
    source_timestamp: float | None = None
    age_seconds: float | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ModelLimitCalibration:
    """Typed result of resolving provider output-limit metadata."""

    provider: str
    model_id: str
    status: ModelLimitCalibrationStatus
    source: str
    provider_max_output_tokens: int | None = None
    context_window_tokens: int | None = None
    limits: ModelLimits | None = None
    source_timestamp: float | None = None
    cache_age_seconds: float | None = None
    detail: str | None = None


def calibrate_model_limits(
    *,
    provider: str,
    model_id: str,
    snapshot: ModelLimitMetadataSnapshot,
) -> ModelLimitCalibration:
    """Resolve model-limit metadata into an explicit calibration result."""

    if snapshot.data is None:
        return _result(
            provider=provider,
            model_id=model_id,
            snapshot=snapshot,
            status=ModelLimitCalibrationStatus.OFFLINE_NO_CACHE,
            detail=snapshot.error,
        )

    models = _as_mapping(snapshot.data.get("models"))
    if models is None:
        return _result(
            provider=provider,
            model_id=model_id,
            snapshot=snapshot,
            status=ModelLimitCalibrationStatus.INVALID_METADATA,
            detail="metadata root is missing a models object",
        )

    model_entry = _as_mapping(models.get(model_id))
    if model_entry is None:
        return _result(
            provider=provider,
            model_id=model_id,
            snapshot=snapshot,
            status=ModelLimitCalibrationStatus.UNKNOWN_MODEL,
            detail=snapshot.error,
        )

    limit = _as_mapping(model_entry.get("limit"))
    if limit is None:
        return _result(
            provider=provider,
            model_id=model_id,
            snapshot=snapshot,
            status=ModelLimitCalibrationStatus.INVALID_METADATA,
            detail="model metadata is missing a limit object",
        )

    context = _positive_int(limit.get("context"))
    output = _positive_int(limit.get("output"))
    if context is None or output is None:
        return _result(
            provider=provider,
            model_id=model_id,
            snapshot=snapshot,
            status=ModelLimitCalibrationStatus.INVALID_METADATA,
            detail="model limit fields must be positive integers",
        )

    limits = ModelLimits(context=context, output=output)
    status = (
        ModelLimitCalibrationStatus.KNOWN_STALE
        if snapshot.is_stale
        else ModelLimitCalibrationStatus.KNOWN_FRESH
    )
    return _result(
        provider=provider,
        model_id=model_id,
        snapshot=snapshot,
        status=status,
        limits=limits,
        provider_max_output_tokens=output,
        context_window_tokens=context,
        detail=snapshot.error,
    )


def _result(
    *,
    provider: str,
    model_id: str,
    snapshot: ModelLimitMetadataSnapshot,
    status: ModelLimitCalibrationStatus,
    provider_max_output_tokens: int | None = None,
    context_window_tokens: int | None = None,
    limits: ModelLimits | None = None,
    detail: str | None = None,
) -> ModelLimitCalibration:
    return ModelLimitCalibration(
        provider=provider,
        model_id=model_id,
        status=status,
        source=snapshot.source,
        provider_max_output_tokens=provider_max_output_tokens,
        context_window_tokens=context_window_tokens,
        limits=limits,
        source_timestamp=snapshot.source_timestamp,
        cache_age_seconds=snapshot.age_seconds,
        detail=detail,
    )


def _as_mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        # models.dev JSON objects have string keys; validate leaf values where consumed.
        return cast("Mapping[str, object]", value)
    return None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        parsed = int(value)
    except TypeError, ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed
