"""Tests that the production InvocationPipeline wires AdaptiveContextEnricher.

After ADR-069 Phase 2 cutover (Task 8) and Phase 2 cleanup (Task 10),
the production pipeline MUST use ``AdaptiveContextEnricher`` and the
legacy ``PreferenceContextEnricherImpl`` class MUST be gone.

See: ADR-069 Decision 1 / Retrofit-Plan steps 7 and 10.
"""

from __future__ import annotations

import pytest

from narrare._app.dependencies_pipeline import get_invocation_pipeline
from narrare_core.ai_invocation.enrichers.adaptive import AdaptiveContextEnricher


class TestPipelineWiresAdaptiveEnricher:
    """Production pipeline MUST use the new adaptive enricher."""

    def test_pipeline_has_at_least_one_adaptive_enricher(self) -> None:
        pipeline = get_invocation_pipeline()
        adaptive_enrichers = [
            e for e in pipeline._enrichers if isinstance(e, AdaptiveContextEnricher)
        ]
        assert len(adaptive_enrichers) >= 1, (
            "Production pipeline must wire at least one AdaptiveContextEnricher. "
            "Found enricher types: " + ", ".join(type(e).__name__ for e in pipeline._enrichers)
        )

    def test_legacy_preference_enricher_class_is_gone(self) -> None:
        """After ADR-069 Phase 2 Task 10, PreferenceContextEnricherImpl is deleted.

        This assertion is a structural guard: importing the legacy class
        MUST fail. If someone re-introduces a same-named class under the
        old module path, this test catches the regression at import time.
        """
        with pytest.raises(ImportError):
            from narrare_core.ai_invocation.enrichers.preferences import (  # noqa: F401
                PreferenceContextEnricherImpl,
            )
