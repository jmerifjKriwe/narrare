"""Uncertain-band adjudicator dependency wiring (ADR-085 P5, RULE-19).

Assembles the adjudicator over the EXISTING ``KBMergeService``
(ADR-085 D5/D7 — the retired merge router's service survives
service-to-service, no route). The merge service — including per-user
model-routing resolution — is built lazily inside the injected factory,
so request DI never touches the routing repositories: analyze stays
LLM-free and config-free unless a REVIEW band actually needs
adjudication (ADR-085 inert by default; cache hits, AUTO-only corpora,
and AI-less deployments never resolve a model).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - FastAPI DI runtime
from narrare.kb.entity_resolution.adjudicator import UncertainBandAdjudicator

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.merge_contracts import KBMergeServiceProtocol


def get_merge_adjudicator(session: SessionDep) -> UncertainBandAdjudicator:
    """Wire the adjudicator with a lazy per-request ``KBMergeService`` factory.

    The factory resolves the caller's model routing (governed
    ``KB_CONSISTENCY`` intent, matching the retired KB-009 merge path)
    only when invoked — i.e. only when REVIEW-band pairs exist on a cache
    miss. Invocation evidence rides the existing pipeline (RULE-22):
    ``KBMergeService`` composes through ``compose_invocation`` unchanged.
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare._app.dependencies_services import get_model_routing_resolver
    from narrare.kb.merge_service import KBMergeService
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.intents import LLMIntent

    async def merge_service_factory(novel_id: UUID, user_id: UUID) -> KBMergeServiceProtocol:
        resolver = get_model_routing_resolver(session)
        resolved = await resolver.resolve(LLMIntent.KB_CONSISTENCY, user_id, novel_id)
        return KBMergeService(
            novel_repo=NovelRepository(session),
            model_registry=get_model_registry(),
            model_config=resolved.config,
            composer=get_composer(),
            kb_repo=KBRepository(session),
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            invocation_pipeline=get_invocation_pipeline(),
        )

    return UncertainBandAdjudicator(merge_service_factory=merge_service_factory)
