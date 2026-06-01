"""Name generation API service — uses LLM registry and prompt composer.

Builds prompts via PromptComposer, calls ModelRegistry, parses structured
JSON responses into GeneratedName objects.  When a KB repository is
injected, existing entity names are passed to the LLM for proactive
dedup and generated names are flagged if they match existing KB entries.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from narrare.generation.schemas import (
    GeneratedName,
    NameGenerateRequest,
    NameGenerateResponse,
)
from narrare_core.writing.budget import cap_to_budget

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)

# Maximum token budget for existing-name dedup context sent to the LLM.
# At ~1.3 tokens/word this allows roughly 350 short entity names.
MAX_EXISTING_NAMES_TOKENS: int = 500

# Mapping from NameType enum values to KB entity_type values.
# NameType uses "place"/"organization"/"item" while the KB CHECK constraint
# uses "location"/"faction"/"object".
_NAME_TYPE_TO_KB_ENTITY: dict[str, str] = {
    "character": "character",
    "place": "location",
    "organization": "faction",
    "item": "object",
}


class NameGeneratorService:
    """Generates names using LLM with style-aware prompts.

    Uses PromptComposer for prompt assembly and ModelRegistry for execution.
    Parses structured JSON responses into GeneratedName objects.  When a
    KB repository is injected, existing entity names are passed to the LLM
    for proactive dedup and generated names are flagged on match.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
        kb_repo: KBRepositoryProtocol | None = None,
    ) -> None:
        self._registry = registry
        self._composer = composer
        self._config = config
        self._api_key = api_key
        self._base_url = base_url
        self._kb_repo = kb_repo

    async def generate_names(self, request: NameGenerateRequest) -> NameGenerateResponse:
        """Generate names based on request parameters.

        Args:
            request: Name generation request with type, name_style, count, etc.

        Returns:
            NameGenerateResponse with generated names and metadata.
        """
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

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
            },
        )

        prompt = await self._composer.build(
            LLMIntent.NAME_GENERATE,
            context,
            user_prompt=self._build_user_prompt(request),
        )

        result: str = await self._registry.run(  # pyright: ignore[reportUnknownVariableType]
            LLMIntent.NAME_GENERATE,
            prompt=prompt.user,
            config=self._config,
            system_prompt=prompt.system,
            api_key=self._api_key,
            base_url=self._base_url,
        )

        names = self._parse_names(result, request)
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

    def _parse_names(self, text: str, request: NameGenerateRequest) -> list[GeneratedName]:
        """Parse LLM JSON response into GeneratedName objects.

        Args:
            text: Raw LLM response text.
            request: Original request for type/name_style metadata.

        Returns:
            List of GeneratedName objects.
        """
        # Strip markdown code fences if present (```json ... ```)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
            cleaned = cleaned[first_newline + 1 :]
            # Remove closing fence (```)
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            raw = json.loads(cleaned)  # type: ignore[reportUnknownVariableType]
        except json.JSONDecodeError:
            logger.warning(
                "name_parse_failed_json",
                text_length=len(text),
                text_preview=text[:200],
            )
            return []

        raw_items: list[object]
        if isinstance(raw, list):
            raw_items = raw  # type: ignore[reportUnknownVariableType]
        elif isinstance(raw, dict):
            names_key = raw.get("names", [])  # type: ignore[reportUnknownVariableType,reportUnknownMemberType]
            raw_items = names_key if isinstance(names_key, list) else [raw]  # type: ignore[reportUnknownVariableType]
        else:
            raw_items = [raw]

        names: list[GeneratedName] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            name_val = item.get("name", "")  # type: ignore[reportUnknownMemberType]
            pron_val = item.get("pronunciation")  # type: ignore[reportUnknownMemberType]
            mean_val = item.get("meaning")  # type: ignore[reportUnknownMemberType]
            names.append(
                GeneratedName(
                    name=str(name_val) if name_val is not None else "",  # type: ignore[reportUnknownArgumentType]
                    pronunciation=str(pron_val) if pron_val is not None else None,  # type: ignore[reportUnknownArgumentType]
                    meaning=str(mean_val) if mean_val is not None else None,  # type: ignore[reportUnknownArgumentType]
                    type=request.name_type.value,
                    name_style=request.name_style,
                ),
            )
        return names

    async def _fetch_existing_names(
        self,
        project_id: UUID,
        name_type: str,
    ) -> list[str]:
        """Fetch existing entity names from the project's KB.

        Queries the KB repository filtered by the mapped entity type.
        Returns an empty list when no KB repository is configured.

        Args:
            project_id: The project (novel) ID to query names for.
            name_type: The NameType value (e.g. "character", "place").

        Returns:
            List of entity names from the KB.
        """
        if self._kb_repo is None:
            return []

        entity_type = _NAME_TYPE_TO_KB_ENTITY.get(name_type)
        entries, total = await self._kb_repo.list_entries(
            novel_id=project_id,
            entity_type=entity_type,
            page_size=1000,
        )

        if total > len(entries):
            logger.warning(
                "kb_names_truncated",
                total=total,
                returned=len(entries),
                hint="Consider pagination if this occurs frequently",
            )

        names = [entry.name for entry in entries]

        # Enforce token budget — truncate the list when the joined
        # string exceeds the allowed budget so prompts never overflow.
        joined = ", ".join(names)
        capped = cap_to_budget(joined, MAX_EXISTING_NAMES_TOKENS)
        result = [n.strip() for n in capped.split(",") if n.strip()]

        if len(result) < len(names):
            logger.info(
                "existing_names_capped",
                original=len(names),
                capped=len(result),
                budget=MAX_EXISTING_NAMES_TOKENS,
            )

        return result

    def _check_duplicates(
        self,
        names: list[GeneratedName],
        existing_names: list[str],
    ) -> list[GeneratedName]:
        """Flag generated names that match existing KB entries.

        Compares case-insensitively with trimmed whitespace.
        Does NOT remove duplicates — only sets is_duplicate=True.

        Args:
            names: Generated names to check.
            existing_names: KB entity names to compare against.

        Returns:
            The same list with is_duplicate flags set where applicable.
        """
        existing_lower = {n.strip().lower() for n in existing_names}
        for name_obj in names:
            if name_obj.name.strip().lower() in existing_lower:
                name_obj.is_duplicate = True
        return names
