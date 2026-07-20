"""Tests that the production InvocationPipeline wires AdaptiveContextEnricher.

After ADR-069 Phase 2 cutover (this task), the production pipeline MUST
use AdaptiveContextEnricher — NOT the legacy PreferenceContextEnricherImpl.

See: ADR-069 Decision 1 / Retrofit-Plan step 7.
"""

from __future__ import annotations

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

    def test_pipeline_does_not_use_legacy_preference_enricher(self) -> None:
        """PreferenceContextEnricherImpl must NOT be wired after cutover.
        This assertion is a regression guard: even after Task 10 deletes
        the class, this test stays as a structural guard (the import will
        fail if someone re-introduces a same-named class)."""
        from narrare_core.ai_invocation.enrichers.preferences import (
            PreferenceContextEnricherImpl,
        )

        pipeline = get_invocation_pipeline()
        for enricher in pipeline._enrichers:
            assert not isinstance(enricher, PreferenceContextEnricherImpl), (
                f"Legacy PreferenceContextEnricherImpl must not be wired. "
                f"Found instance in pipeline: {enricher!r}"
            )
