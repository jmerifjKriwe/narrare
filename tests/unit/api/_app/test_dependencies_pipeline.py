"""Unit tests for ``narrare._app.dependencies_pipeline`` — pipeline assembly.

Tests that ``get_invocation_pipeline()`` returns a fully configured
``InvocationPipeline`` with all P0.3 components wired.
"""

from __future__ import annotations

from unittest.mock import patch

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


class TestNoRealMem0InPipelineTests:
    """Regression: ``get_invocation_pipeline()`` must not create real mem0
    clients (RULE-20).

    ``get_invocation_pipeline()`` delegates to
    ``_get_preference_service_instance()`` which, without the
    ``tests/unit/conftest.py`` isolation fixture, would create a real
    ``AsyncMemory`` / ``QdrantClient`` because mem0 is installed and
    conftest sets dummy API keys.
    """

    def test_pipeline_does_not_call_create_memory_client_sync(self) -> None:
        """get_invocation_pipeline() must not trigger real mem0 client creation."""
        import narrare._app.dependencies_prompts as prompts_mod

        # Reset preference-service singleton so the spy observes a fresh
        # assembly path, not a cached result.
        prompts_mod._preference_service_instance = None
        prompts_mod._preference_service_init_tried = False
        pipeline_mod.get_invocation_pipeline.cache_clear()

        with patch("narrare_core.memory.mem0_client.create_memory_client_sync") as spy_create:
            pipeline_mod.get_invocation_pipeline()

        assert not spy_create.called, (
            "get_invocation_pipeline() triggered create_memory_client_sync() — "
            "a real mem0/Qdrant client would be created. "
            "Unit tests must never create real external resources (RULE-20)."
        )
