"""Writing module dependency injection — WebSocket turn service factory.

Creates the :class:`WritingTurnService` with wired invocation pipeline,
run-limit resolver, and shared registries (ADR-045 Decision 6).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import (
    get_composer,
    get_invocation_pipeline,
    get_model_registry,
)

if TYPE_CHECKING:
    from narrare.writing.ws_turn_service import WritingTurnService
    from narrare_core.llm import ResolvedModelConfig


def get_writing_turn_service(
    config: ResolvedModelConfig,
) -> WritingTurnService:
    """Create a WritingTurnService for a WebSocket session.

    Wires the shared invocation pipeline, model registry, and a fresh
    run-limit resolver for per-connection streaming turns.

    Args:
        config: The per-request resolved model configuration.

    Returns:
        Configured :class:`WritingTurnService`.
    """
    from narrare.writing.ws_turn_service import WritingTurnService
    from narrare_core.llm.run_limits import DefaultRunLimitResolver

    return WritingTurnService(
        composer=get_composer(),
        invocation_pipeline=get_invocation_pipeline(),
        registry=get_model_registry(),
        config=config,
        run_limit_resolver=DefaultRunLimitResolver(),
    )
