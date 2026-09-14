"""Name generation API service — uses LLM registry and prompt composer.

Builds prompts via PromptComposer, calls ModelRegistry, parses structured
JSON responses into GeneratedName objects.  When a KB repository is
injected, existing entity names are passed to the LLM for proactive
dedup and generated names are flagged if they match existing KB entries.

Ownership (IDOR remediation S12b): ``generate_names`` gates the request's
project on the caller BEFORE ``_fetch_existing_names`` and any LLM call —
foreign and unknown projects are indistinguishable (``NotFoundError`` → 404).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import structlog

from narrare.generation._name_invocation import compose_name_invocation
from narrare.generation.name_dedup import (
    DEFAULT_NAME_DEDUP_PAGE_SIZE,
    fetch_existing_names,
    flag_duplicates,
)
from narrare.generation.name_parsing import parse_generated_names
from narrare.generation.schemas import (
    GeneratedName,
    NameGenerateRequest,
    NameGenerateResponse,
)
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare._app.dependencies_services import ModelResolution
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class NameGeneratorService:
    """Generates names using LLM with style-aware prompts.

    Uses PromptComposer for prompt assembly and ModelRegistry for execution.
    Parses structured JSON responses into GeneratedName objects.  When a
    KB repository is injected, existing entity names are passed to the LLM
    for proactive dedup and generated names are flagged on match.

    Args:
        registry: ModelRegistry for LLM execution.
        composer: PromptComposer for prompt assembly.
        model_resolution: Lazy per-user model resolution (ADR-086) — the
            routing cascade resolves on first use, never at construction.
        novel_repo: Novel repository — the project ownership gate (IDOR S12b).
        kb_repo: Optional KB repository for name dedup.
        invocation_pipeline: Optional pipeline for invocation evidence.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        composer: PromptComposer,
        model_resolution: ModelResolution,
        novel_repo: NovelRepositoryProtocol,
        kb_repo: KBRepositoryProtocol | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._registry = registry
        self._composer = composer
        self._model_resolution = model_resolution
        self._resolved: ResolvedModel | None = None
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo
        self._invocation_pipeline = invocation_pipeline

    async def ensure_resolved(self) -> ResolvedModel:
        """Resolve the per-user model routing once; idempotent (ADR-086).

        First call resolves via the injected ``ModelResolution`` and
        caches the triple; repeat calls return the cached value without
        re-running the cascade. Errors propagate loudly and are never
        cached (RULE-11): ``ConfigurationError`` (``NO_AI_PROVIDER``)
        surfaces as a 400 on this AI-mandatory endpoint.
        """
        if self._resolved is None:
            self._resolved = await self._model_resolution.resolve()
        return self._resolved

    async def generate_names(
        self, request: NameGenerateRequest, user_id: UUID
    ) -> NameGenerateResponse:
        """Generate names based on request parameters.

        The FIRST statement gates the request's project on the caller
        (Pattern B, IDOR S12b): a foreign or unknown project raises
        ``NotFoundError`` BEFORE the project's KB entity names are read
        (they would otherwise flow into the LLM prompt) and before any
        LLM call.

        Args:
            request: Name generation request with type, name_style, count, etc.
            user_id: The caller's identity — ownership gate input.

        Returns:
            NameGenerateResponse with generated names and metadata.

        Raises:
            NotFoundError: The project is unknown or owned by another user —
                both cases are indistinguishable by design (→ 404).
            ConfigurationError: The per-user routing cascade finds no
                configured provider (ADR-086 first-use resolution, RULE-11
                loud propagation — AI-mandatory endpoint).
        """
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        # Ownership gate (IDOR S12b) — BEFORE _fetch_existing_names and any
        # LLM call. Foreign KB names must never reach the prompt.
        novel = await self._novel_repo.get_by_id(request.project_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(request.project_id))

        # ADR-086 L14: first-use lazy resolve — the ownership gates above
        # stay ahead of resolution (eager-world precedence), and the
        # generation sampling overrides layer onto the resolved config
        # exactly as the eager factory did (timing-only migration).
        resolved_model = await self.ensure_resolved()
        config = replace(resolved_model.config, temperature=0.8, max_tokens=2000)

        # Fetch existing KB names BEFORE the LLM call for proactive dedup.
        existing_names = await self._fetch_existing_names(
            project_id=request.project_id,
            name_type=request.name_type.value,
        )

        context = PromptContext(
            language=request.explanation_language,
            mode="names",
            extra={
                "name_style": request.name_style,
                "name_type": request.name_type.value,
                "count": str(request.count),
                "gender": request.gender.value,
                "existing_names": ", ".join(existing_names),
                "explanation_language": request.explanation_language,
            },
        )

        # ADR-048: route through the InvocationPipeline (Mode 2 -- the name
        # generator composes its prompt inline). prepare() enriches the context
        # (preferences, kb_suggested) and finalize() records correlated evidence.
        # pipeline=None is a backward-compatible no-op returning the original context.
        enriched_context = await compose_name_invocation(
            self._invocation_pipeline,
            project_id=request.project_id,
            language=request.explanation_language,
            prompt_context=context,
        )

        prompt = await self._composer.build(
            LLMIntent.NAME_GENERATE,
            enriched_context,
            user_prompt=self._build_user_prompt(request),
        )

        result: str = await self._registry.run(
            LLMIntent.NAME_GENERATE,
            prompt=prompt.user,
            config=config,
            system_prompt=prompt.system,
            api_key=resolved_model.api_key,
            base_url=resolved_model.base_url,
        )

        names = parse_generated_names(result, request)
        names = self._check_duplicates(names, existing_names)

        logger.info(
            "names_generated",
            name_type=request.name_type.value,
            name_style=request.name_style,
            count=len(names),
            duplicates=sum(1 for n in names if n.is_duplicate),
        )

        return NameGenerateResponse(
            names=names,
            count=len(names),
            name_style=request.name_style,
            name_type=request.name_type.value,
        )

    def _build_user_prompt(self, request: NameGenerateRequest) -> str:
        """Build the user-facing prompt for name generation."""
        return (
            f"Generate {request.count} {request.name_type.value} names "
            f"for a {request.name_style} setting. "
            f"Gender preference: {request.gender.value}. "
            f"Language: {request.explanation_language}. "
            f"Return as JSON array with fields: name, pronunciation, meaning."
        )

    async def _fetch_existing_names(
        self,
        project_id: UUID,
        name_type: str,
    ) -> list[str]:
        """Fetch existing entity names from the project's KB.

        Delegates to :func:`narrare.generation.name_dedup.fetch_existing_names`,
        wiring the governed page size by name (single definition site —
        the defaults structural pin inspects this seam).

        Args:
            project_id: The project (novel) ID to query names for.
            name_type: The NameType value (e.g. "character", "place").

        Returns:
            List of entity names from the KB, capped to the token budget.
        """
        return await fetch_existing_names(
            self._kb_repo,
            project_id,
            name_type,
            page_size=DEFAULT_NAME_DEDUP_PAGE_SIZE,
        )

    def _check_duplicates(
        self,
        names: list[GeneratedName],
        existing_names: list[str],
    ) -> list[GeneratedName]:
        """Flag generated names that match existing KB entries.

        Delegates to :func:`narrare.generation.name_dedup.flag_duplicates`.
        """
        return flag_duplicates(names, existing_names)
