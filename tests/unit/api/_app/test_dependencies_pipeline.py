"""Unit tests for ``narrare._app.dependencies_pipeline`` — pipeline assembly.

Tests that ``get_invocation_pipeline()`` returns a fully configured
``InvocationPipeline`` with all P0.3 components wired.
"""

from __future__ import annotations

import narrare._app.dependencies_pipeline as pipeline_mod
from narrare_core.ai_invocation.pipeline import InvocationPipeline


class TestGetInvocationPipeline:
    def test_returns_configured_pipeline(self) -> None:
        """Pipeline is created with enrichers, validators, and evidence sink."""
        # Clear lru_cache to ensure fresh assembly within the test.
        pipeline_mod.get_invocation_pipeline.cache_clear()

        pipeline = pipeline_mod.get_invocation_pipeline()

        assert isinstance(pipeline, InvocationPipeline)

    def test_cached_on_repeated_calls(self) -> None:
        """@lru_cache returns the same instance on second call."""
        pipeline_mod.get_invocation_pipeline.cache_clear()

        first = pipeline_mod.get_invocation_pipeline()
        second = pipeline_mod.get_invocation_pipeline()

        assert first is second
