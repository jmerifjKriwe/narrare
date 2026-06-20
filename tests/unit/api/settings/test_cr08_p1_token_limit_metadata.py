"""CR-08 P1 metadata tests — catalogue, calibration, suitability exposure.

Split from ``test_cr08_p1_token_profile_contract.py`` for RULE-04 compliance.
Covers the response-metadata requirements (policy D4/D5/D6):

* the Core-derived profile catalogue and caps,
* typed calibration evidence (unknown / offline / provider-too-small), and
* model suitability warnings and hard blocks.

The ``TokenLimitsMetadataService`` accepts an injectable calibration provider,
so these tests are deterministic and require no network.
"""

from __future__ import annotations

from narrare_core.llm.model_calibration import (
    ModelLimitCalibration,
    ModelLimitCalibrationStatus,
)
from narrare_core.llm.token_profiles import (
    PROFILE_OUTPUT_LIMITS,
    TOKEN_OUTPUT_ABSOLUTE_MAX,
    TOKEN_OUTPUT_UX_RECOMMENDED_MAX,
    public_token_profile_values,
)


def _offline_calibration(provider: str, model_id: str) -> ModelLimitCalibration:
    """A deterministic offline calibration used across the metadata tests."""

    return ModelLimitCalibration(
        provider=provider,
        model_id=model_id,
        status=ModelLimitCalibrationStatus.OFFLINE_NO_CACHE,
        source="test",
    )


# ======================================================================
# D4 — response catalogue metadata
# ======================================================================


class TestResponseCatalogueMetadata:
    """The response must expose the Core-derived catalogue and caps."""

    def test_catalogue_contains_exactly_public_profiles(self) -> None:
        from narrare.settings.token_limits.metadata_service import (
            TokenLimitsMetadataService,
        )

        catalogue = TokenLimitsMetadataService().get_catalogue()
        catalogue_values = {p.value for p in catalogue.profiles}
        assert catalogue_values == set(public_token_profile_values())
        assert "conservative" not in catalogue_values

    def test_catalogue_preset_limits_match_core(self) -> None:
        from narrare.settings.token_limits.metadata_service import (
            TokenLimitsMetadataService,
        )

        catalogue = TokenLimitsMetadataService().get_catalogue()
        for entry in catalogue.profiles:
            if entry.is_custom:
                assert entry.preset_output_limit is None
            else:
                assert entry.preset_output_limit == PROFILE_OUTPUT_LIMITS[entry.value]

    def test_catalogue_exposes_core_caps(self) -> None:
        from narrare.settings.token_limits.metadata_service import (
            TokenLimitsMetadataService,
        )

        catalogue = TokenLimitsMetadataService().get_catalogue()
        assert catalogue.absolute_max == TOKEN_OUTPUT_ABSOLUTE_MAX
        assert catalogue.ux_recommended_max == TOKEN_OUTPUT_UX_RECOMMENDED_MAX


# ======================================================================
# D5 — calibration metadata exposure
# ======================================================================


class TestCalibrationMetadataExposure:
    """Calibration evidence (unknown / offline) is exposed."""

    def test_offline_calibration_maps_to_metadata(self) -> None:
        from narrare.settings.token_limits.metadata_service import (
            TokenLimitsMetadataService,
        )

        service = TokenLimitsMetadataService(calibration_provider=_offline_calibration)
        meta = service.get_calibration("openai", "gpt-4o")

        assert meta.status == ModelLimitCalibrationStatus.OFFLINE_NO_CACHE.value
        assert meta.provider_max_output_tokens is None

    def test_unknown_model_calibration_maps_to_metadata(self) -> None:
        from narrare.settings.token_limits.metadata_service import (
            TokenLimitsMetadataService,
        )

        def _unknown(provider: str, model_id: str) -> ModelLimitCalibration:
            return ModelLimitCalibration(
                provider=provider,
                model_id=model_id,
                status=ModelLimitCalibrationStatus.UNKNOWN_MODEL,
                source="test",
            )

        service = TokenLimitsMetadataService(calibration_provider=_unknown)
        meta = service.get_calibration("openai", "ghost-model")

        assert meta.status == ModelLimitCalibrationStatus.UNKNOWN_MODEL.value

    def test_known_fresh_calibration_exposes_provider_max(self) -> None:
        from narrare.settings.token_limits.metadata_service import (
            TokenLimitsMetadataService,
        )

        def _fresh(provider: str, model_id: str) -> ModelLimitCalibration:
            return ModelLimitCalibration(
                provider=provider,
                model_id=model_id,
                status=ModelLimitCalibrationStatus.KNOWN_FRESH,
                source="test",
                provider_max_output_tokens=16384,
                context_window_tokens=200000,
            )

        service = TokenLimitsMetadataService(calibration_provider=_fresh)
        meta = service.get_calibration("anthropic", "claude-sonnet-4-5")

        assert meta.status == ModelLimitCalibrationStatus.KNOWN_FRESH.value
        assert meta.provider_max_output_tokens == 16384
        assert meta.context_window_tokens == 200000


# ======================================================================
# D6 — suitability warning/block exposure
# ======================================================================


class TestSuitabilityWarningExposure:
    """Suitability warnings surface for provider-too-small and unknown/offline."""

    def test_provider_too_small_blocks_and_exposes_warning(self) -> None:
        from narrare.settings.token_limits.metadata_service import (
            TokenLimitsMetadataService,
        )
        from narrare_core.llm.intents import LLMIntent

        def _tiny(provider: str, model_id: str) -> ModelLimitCalibration:
            return ModelLimitCalibration(
                provider=provider,
                model_id=model_id,
                status=ModelLimitCalibrationStatus.KNOWN_FRESH,
                source="test",
                provider_max_output_tokens=64,
                limits=None,
            )

        service = TokenLimitsMetadataService(calibration_provider=_tiny)
        result = service.evaluate_suitability(
            provider="openai",
            model_id="tiny",
            intent=LLMIntent.WRITE,
            requested_output_tokens=8000,
        )

        assert result.severity == "hard_block"
        assert result.is_allowed is False
        assert any(i.code == "provider_cap_below_minimum_floor" for i in result.issues)

    def test_offline_calibration_emits_warning(self) -> None:
        from narrare.settings.token_limits.metadata_service import (
            TokenLimitsMetadataService,
        )
        from narrare_core.llm.intents import LLMIntent

        service = TokenLimitsMetadataService(calibration_provider=_offline_calibration)
        result = service.evaluate_suitability(
            provider="openai",
            model_id="gpt-4o",
            intent=LLMIntent.WRITE,
            requested_output_tokens=8000,
        )

        assert result.severity in {"warning", "advisory"}
        assert any(i.code.startswith("calibration_") for i in result.issues)

    def test_known_fresh_adequate_model_is_allowed(self) -> None:
        from narrare.settings.token_limits.metadata_service import (
            TokenLimitsMetadataService,
        )
        from narrare_core.llm.intents import LLMIntent

        def _adequate(provider: str, model_id: str) -> ModelLimitCalibration:
            return ModelLimitCalibration(
                provider=provider,
                model_id=model_id,
                status=ModelLimitCalibrationStatus.KNOWN_FRESH,
                source="test",
                provider_max_output_tokens=16384,
                context_window_tokens=200000,
            )

        service = TokenLimitsMetadataService(calibration_provider=_adequate)
        result = service.evaluate_suitability(
            provider="anthropic",
            model_id="claude",
            intent=LLMIntent.WRITE,
            requested_output_tokens=8000,
            model_capability_tier="creative",
        )

        assert result.is_allowed is True
        assert result.severity != "hard_block"
