"""Shared test helpers for KBMergeService tests (RULE-04 split).

Provides fakes and fixtures used by both
``test_merge_service.py`` (Mode 1 behavioural) and
``test_merge_service_compliance.py`` (source-level regression + RULE-11).

Mirrors the ``_timeline_extraction_test_helpers.py`` /
``_character_arc_test_helpers.py`` pattern (ADR-054 precedent).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from narrare_core.agents.merge_types import MergeOutput
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare.kb.merge_service import KBMergeService
    from narrare.kb.schemas_merge import MergeRequest
    from narrare_core.llm.model_config import ResolvedModelConfig

# ---------------------------------------------------------------------------
# Fakes (avoid bare MagicMock for domain contracts — RULE-TEST-01)
# ---------------------------------------------------------------------------


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model."""

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))


class FakeComposer:
    """Fake PromptComposer for DI wiring.

    The service routes through ``compose_invocation`` (which calls
    ``composer.build`` internally), so this fake only needs to exist for DI
    wiring — its ``build`` is never reached when ``compose_invocation`` is
    patched. Kept as a real object (not a bare MagicMock) so the service's
    ``composer is None`` guard is satisfied.
    """

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="COMPOSED-MERGE-SYSTEM", user="")
        )


class FakeComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1).

    The service only reads ``invocation.composed_prompt`` (Mode 1 invariant),
    so a lightweight class with that attribute is sufficient and avoids
    constructing the full ``prepared``/``finalized`` pipeline objects.
    """

    def __init__(self, system: str = "COMPOSED-MERGE-SYSTEM", user: str = "") -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(system=system, user=user)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_novel(**overrides: object) -> MagicMock:
    """Create a mock novel with the attributes KBMergeService reads."""
    from narrare.novels.models import Novel

    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "Fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=Novel)
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def make_merge_output() -> MergeOutput:
    """Build a fake KBMergeAgent.run result with no decisions."""
    return MergeOutput(merge_decisions=[], overall_notes="No merge candidates found.")


def make_request(
    *,
    entity_type: str = "character",
    candidate_pairs: list[dict[str, object]] | None = None,
) -> MergeRequest:
    """Build a MergeRequest with one candidate pair by default."""
    from narrare.kb.schemas_merge import MergeRequest

    return MergeRequest(
        entity_type=entity_type,
        candidate_pairs=candidate_pairs or [{"name_a": "Alice", "name_b": "Alis"}],
    )


def make_service(
    composer: FakeComposer,
    config: ResolvedModelConfig,
) -> KBMergeService:
    """Build a KBMergeService wired for Mode 1 prompt resolution."""
    from narrare.kb.merge_service import KBMergeService

    novel_repo = AsyncMock()
    novel_repo.get_by_id = AsyncMock(return_value=make_novel())
    return KBMergeService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_config=config,
        composer=composer,  # type: ignore[arg-type]
    )
