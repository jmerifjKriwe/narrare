"""KB Consistency Analyzer — LLM-driven entry-internal consistency analysis.

For each entity, builds a PromptContext and calls the LLM via
``ModelRegistry.run()`` to detect internal field contradictions.
Returns a list of :class:`ConsistencyIssue` objects.

Uses PromptComposer (RULE-02).  No dedicated pydantic-ai Agent —
single-shot ``registry.run()`` with structured output.

See:
    :class:`narrare.kb.consistency_service.KBConsistencyService`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from narrare.kb.worldbuilding_contracts import (
    ConsistencyCategory,
    ConsistencyIssue,
    WorldbuildingSeverity,
)
from narrare.kb.worldbuilding_entity_assembly import list_entities
from narrare_core.kb.schemas.registry import get_schema
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM Output Types (internal — not part of the public API)
# ---------------------------------------------------------------------------


class _EntryInternalIssue(BaseModel):
    """Single entry-internal consistency issue from LLM output."""

    field_keys: list[str]
    description: str
    contradiction: str
    suggested_resolution: str
    severity: str  # "critical" | "major" | "minor"
    confidence: float = Field(ge=0.0, le=1.0)


class _EntryInternalOutput(BaseModel):
    """Structured LLM output for entry-internal consistency check."""

    issues: list[_EntryInternalIssue]
    assessment: str


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class KBConsistencyAnalyzer:
    """Entry-internal consistency analysis via LLM.

    For each entity, builds a prompt with entry content and template
    structure, calls the LLM via ``ModelRegistry.run()``, and maps
    results to :class:`ConsistencyIssue` objects.

    Args:
        kb_repo: KB entry repository for listing entities.
        registry: Model registry for LLM calls (RULE-01).
        config: Resolved model configuration.
        composer: PromptComposer for building system prompts (RULE-02).
    """

    def __init__(
        self,
        kb_repo: KBRepositoryProtocol,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        composer: PromptComposer,
    ) -> None:
        self._kb_repo = kb_repo
        self._registry = registry
        self._config = config
        self._composer = composer

    async def analyze_entries(
        self,
        novel_id: UUID,
        entity_types: list[str] | None,
    ) -> tuple[list[ConsistencyIssue], int]:
        """Run entry-internal consistency check on all matching entities.

        Args:
            novel_id: The project to analyze.
            entity_types: Optional filter by entity type.

        Returns:
            Tuple of (issues found, entity count analyzed).
        """
        entities = await list_entities(self._kb_repo, novel_id, entity_types)
        if not entities:
            return [], 0

        issues: list[ConsistencyIssue] = []
        idx = 0

        for entity in entities:
            try:
                entry_issues = await self._analyze_entry(entity)
            except Exception:
                logger.warning(
                    "entry_internal_analysis_failed",
                    entry_id=str(entity.id),
                    entry_name=entity.name,
                    exc_info=True,
                )
                continue

            for raw in entry_issues:
                issues.append(
                    ConsistencyIssue(
                        finding_index=idx,
                        category=ConsistencyCategory.ENTRY_INTERNAL,
                        entity_ids=[str(entity.id)],
                        entity_names=[entity.name],
                        description=raw.description,
                        contradiction=raw.contradiction,
                        suggested_resolution=raw.suggested_resolution,
                        severity=_safe_severity(raw.severity),
                        confidence=raw.confidence,
                    )
                )
                idx += 1

        logger.info(
            "entry_internal_analysis_complete",
            novel_id=str(novel_id),
            entity_count=len(entities),
            issues_found=len(issues),
        )
        return issues, len(entities)

    async def _analyze_entry(
        self,
        entity: KBEntry,
    ) -> list[_EntryInternalIssue]:
        """Analyze a single entry for internal field contradictions.

        Builds the prompt context, resolves the system prompt via
        PromptComposer, and calls the LLM with structured output.
        """
        entry_content = _build_entry_content(entity)
        template_structure = _build_template_structure(entity.entity_type)

        ctx = PromptContext(
            language="en",
            mode=LLMIntent.KB_CONSISTENCY.value,
            entity_type=entity.entity_type,
            entity_name=entity.name,
            extra={
                "entry_content": str(entry_content),
                "template_structure": str(template_structure),
            },
        )
        composed = await self._composer.build(LLMIntent.KB_CONSISTENCY, ctx)

        result: _EntryInternalOutput = await self._registry.run(
            intent=LLMIntent.KB_CONSISTENCY,
            prompt=composed.user,
            config=self._config,
            system_prompt=composed.system,
            output_type=_EntryInternalOutput,
        )
        return result.issues


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_entry_content(entity: KBEntry) -> dict[str, object]:
    """Build entry content dict for the prompt."""
    return {
        "name": entity.name,
        "entity_type": entity.entity_type,
        "metadata": dict(entity.metadata_ or {}),
        "body": (entity.body[:5000] if entity.body else ""),
        "tags": list(entity.tags) if entity.tags else [],
    }


def _build_template_structure(entity_type: str) -> dict[str, str]:
    """Build field-key to label mapping for the entity type."""
    schema_cls = get_schema(entity_type)
    return {
        name: (info.description or name.replace("_", " ").title())
        for name, info in schema_cls.model_fields.items()
    }


def _safe_severity(raw: str) -> WorldbuildingSeverity:
    """Parse severity, defaulting to MAJOR."""
    try:
        return WorldbuildingSeverity(raw)
    except ValueError:
        return WorldbuildingSeverity.MAJOR
