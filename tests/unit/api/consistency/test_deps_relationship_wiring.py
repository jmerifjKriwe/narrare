"""Factory relationship-wiring pin for the consistency deps (FIND-001).

Proves ``consistency/deps.get_consistency_service`` injects a
``RelationshipRepository`` into ``ConsistencyCheckerService``. The
downstream consumption chain is live — service →
``collect_check_context`` → ``ConsistencyDeps.kb_relationships`` →
``kb_relationships`` prompt variable (behavior pinned in
``test_checker_context.py`` / ``test_checker_service.py``) — so a
missing factory injection silently degrades relationship-aware
checking to an empty string.

Regression origin: ADR-086 L13 removed the CR-03 wiring (commit
``6fa0668d``) on a false "dead wiring (never injected)" premise;
``6dba8e18`` (pre-L13) provably injected ``relationship_repo``. This
pin makes a repeat of that drop fail loudly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl


async def test_factory_injects_relationship_repository() -> None:
    """get_consistency_service wires RelationshipRepository (FIND-001)."""
    from narrare.consistency.deps import get_consistency_service
    from narrare.kb.relationship_repository import RelationshipRepository

    session = MagicMock(spec=AsyncSession, name="session")
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock()

    with (
        patch(
            "narrare.consistency.deps.get_model_routing_resolver",
            return_value=resolver,
        ),
        patch(
            "narrare._app.dependencies.get_model_registry",
            return_value=MagicMock(spec=True, name="ModelRegistry"),
        ),
        patch(
            "narrare._app.dependencies.get_composer",
            return_value=MagicMock(spec=True, name="PromptComposer"),
        ),
        patch(
            "narrare._app.dependencies.get_invocation_pipeline",
            return_value=MagicMock(spec=True, name="InvocationPipeline"),
        ),
        patch(
            "narrare._app.config.get_settings",
            return_value=MagicMock(spec=True, name="Settings"),
        ),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=MagicMock(spec=True, name="TokenLimitsService"),
        ),
    ):
        service = await get_consistency_service(
            session=session,
            user_id=str(uuid4()),
            novel_id=uuid4(),
        )

    assert isinstance(service._relationship_repo, RelationshipRepository)
