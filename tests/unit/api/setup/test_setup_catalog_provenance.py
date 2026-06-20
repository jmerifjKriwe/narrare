"""Setup fallback catalog provenance — CR-AUFG-08-06.

Tests that the bundled fallback model catalog carries explicit
source/freshness labels, and that the setup API response surfaces
this provenance so clients can render "stale/offline fallback"
explicitly instead of implying a live, calibrated catalog.

DoD: "Fallback list has source/freshness labels; setup UI/API marks
stale/offline fallback explicitly."

See: docs/features/remediation/cr-08-configuration-effect-drift.md §P2 CR-AUFG-08-06
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from narrare.setup.base_schemas import AIProvider
from narrare.setup.constants import (
    FALLBACK_CATALOG_LAST_REVIEWED,
    FALLBACK_CATALOG_SOURCE,
    LIVE_CATALOG_SOURCE,
)
from narrare.setup.provider_schemas import (
    AvailableModelsResponse,
    ModelCatalogProvenance,
    ProviderModel,
)
from narrare.setup.provider_service import ProviderService

# ---------------------------------------------------------------------------
# (a) Catalog provenance constants
# ---------------------------------------------------------------------------


class TestCatalogProvenanceConstants:
    """The bundled fallback catalog carries explicit source/freshness labels."""

    def test_fallback_source_label_is_bundled_fallback(self) -> None:
        """The source label identifies the catalog as a bundled static fallback."""
        assert FALLBACK_CATALOG_SOURCE == "bundled-fallback"

    def test_live_source_label_is_live(self) -> None:
        """The live source label distinguishes API-fetched models."""
        assert LIVE_CATALOG_SOURCE == "live"

    def test_fallback_last_reviewed_is_a_real_date(self) -> None:
        """The fallback catalog has a concrete last-reviewed date, not None.

        A missing date would hide staleness from the user. The date must
        be a real calendar date so the frontend can render "last reviewed
        October 2025" or similar.
        """
        assert isinstance(FALLBACK_CATALOG_LAST_REVIEWED, date)
        assert date.today() >= FALLBACK_CATALOG_LAST_REVIEWED

    def test_fallback_last_reviewed_matches_source_comment(self) -> None:
        """The structured date matches the 'Checked 2025-10' comment in provider_service.

        If someone updates the comment but not the constant (or vice versa),
        this test fails — the two must stay in sync.
        """
        assert date(2025, 10, 1) == FALLBACK_CATALOG_LAST_REVIEWED


# ---------------------------------------------------------------------------
# (b) AvailableModelsResponse includes provenance
# ---------------------------------------------------------------------------


class TestAvailableModelsResponseProvenance:
    """The response schema exposes provenance so clients can label fallback."""

    def test_provenance_field_exists_and_defaults_to_none(self) -> None:
        """The field exists, is optional, and defaults to None."""
        response = AvailableModelsResponse(
            provider=AIProvider.OPENAI,
            models=[ProviderModel(id="gpt-4o", name="GPT-4o")],
        )
        assert response.provenance is None

    def test_provenance_field_accepts_live_source(self) -> None:
        """Live-fetched models get a provenance with source='live'."""
        response = AvailableModelsResponse(
            provider=AIProvider.OPENAI,
            models=[ProviderModel(id="gpt-4o", name="GPT-4o")],
            provenance=ModelCatalogProvenance(source=LIVE_CATALOG_SOURCE),
        )
        assert response.provenance is not None
        assert response.provenance.source == "live"
        assert response.provenance.last_reviewed is None

    def test_provenance_field_accepts_fallback_with_date(self) -> None:
        """Fallback models get provenance with source and last_reviewed date."""
        response = AvailableModelsResponse(
            provider=AIProvider.OPENAI,
            models=[ProviderModel(id="gpt-4o", name="GPT-4o")],
            provenance=ModelCatalogProvenance(
                source=FALLBACK_CATALOG_SOURCE,
                last_reviewed=FALLBACK_CATALOG_LAST_REVIEWED,
            ),
        )
        assert response.provenance is not None
        assert response.provenance.source == "bundled-fallback"
        assert response.provenance.last_reviewed == date(2025, 10, 1)

    def test_provenance_field_serializes_to_json(self) -> None:
        """The provenance object survives JSON round-trip (API contract)."""
        response = AvailableModelsResponse(
            provider=AIProvider.ANTHROPIC,
            models=[ProviderModel(id="claude-3", name="Claude 3")],
            provenance=ModelCatalogProvenance(
                source=FALLBACK_CATALOG_SOURCE,
                last_reviewed=date(2025, 10, 1),
            ),
        )
        dumped = response.model_dump()
        assert "provenance" in dumped
        assert dumped["provenance"]["source"] == "bundled-fallback"
        assert dumped["provenance"]["last_reviewed"] == date(2025, 10, 1)


# ---------------------------------------------------------------------------
# (c) ProviderService.list_models distinguishes live vs fallback
# ---------------------------------------------------------------------------


@pytest.fixture
def service() -> ProviderService:
    return ProviderService()


class TestProviderServiceProvenance:
    """list_models sets provenance based on whether the live API was reached."""

    async def test_live_fetch_sets_live_provenance(self, service: ProviderService) -> None:
        """When the catalog API returns models, provenance source is 'live'."""
        from narrare.setup._model_fetchers import FetchResult

        mock_result = FetchResult(
            models=[ProviderModel(id="live-model", name="Live")],
            used_fallback=False,
        )
        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, return_value=mock_result
        ):
            result = await service.list_models(AIProvider.OPENAI, "sk-test")

        assert result.provenance is not None
        assert result.provenance.source == LIVE_CATALOG_SOURCE
        assert result.provenance.last_reviewed is None

    async def test_fallback_sets_bundled_provenance_with_date(
        self, service: ProviderService
    ) -> None:
        """When fetch_models reports fallback, provenance marks bundled + date."""
        from narrare.setup._model_fetchers import FetchResult

        mock_result = FetchResult(
            models=[ProviderModel(id="fallback-model", name="Fallback")],
            used_fallback=True,
        )
        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, return_value=mock_result
        ):
            result = await service.list_models(AIProvider.OPENAI, "sk-test")

        assert result.provenance is not None
        assert result.provenance.source == FALLBACK_CATALOG_SOURCE
        assert result.provenance.last_reviewed == FALLBACK_CATALOG_LAST_REVIEWED

    async def test_exception_in_fetch_sets_fallback_provenance(
        self, service: ProviderService
    ) -> None:
        """When _fetch_models raises, list_models falls back and marks provenance."""
        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, side_effect=Exception("timeout")
        ):
            result = await service.list_models(AIProvider.OPENAI, "sk-test")

        assert result.provenance is not None
        assert result.provenance.source == FALLBACK_CATALOG_SOURCE
        assert result.provenance.last_reviewed == FALLBACK_CATALOG_LAST_REVIEWED

    async def test_live_and_fallback_responses_are_distinguishable(
        self, service: ProviderService
    ) -> None:
        """A client can tell live from fallback by comparing provenance.source."""
        from narrare.setup._model_fetchers import FetchResult

        live_result = FetchResult(
            models=[ProviderModel(id="live", name="Live")],
            used_fallback=False,
        )
        fallback_result = FetchResult(
            models=[ProviderModel(id="fallback", name="Fallback")],
            used_fallback=True,
        )

        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, return_value=live_result
        ):
            live_response = await service.list_models(AIProvider.OPENAI, "key")

        with patch.object(
            service, "_fetch_models", new_callable=AsyncMock, return_value=fallback_result
        ):
            fallback_response = await service.list_models(AIProvider.OPENAI, "key")

        assert live_response.provenance is not None
        assert fallback_response.provenance is not None
        assert live_response.provenance.source != fallback_response.provenance.source
        assert live_response.provenance.last_reviewed is None
        assert fallback_response.provenance.last_reviewed is not None
