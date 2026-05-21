"""Name generation API service — uses LLM registry and prompt composer.

Builds prompts via PromptComposer, calls ModelRegistry, parses structured
JSON responses into GeneratedName objects. Includes placeholder KB
dedup check for future integration.
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

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class NameGeneratorService:
    """Generates names using LLM with culture-aware prompts.

    Uses PromptComposer for prompt assembly and ModelRegistry for execution.
    Parses structured JSON responses into GeneratedName objects.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._registry = registry
        self._composer = composer
        self._config = config
        self._api_key = api_key
        self._base_url = base_url

    async def generate_names(self, request: NameGenerateRequest) -> NameGenerateResponse:
        """Generate names based on request parameters.

        Args:
            request: Name generation request with type, culture, count, etc.

        Returns:
            NameGenerateResponse with generated names and metadata.
        """
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        context = PromptContext(
            language=request.language,
            mode="names",
            extra={
                "culture": request.culture,
                "name_type": request.name_type.value,
                "count": str(request.count),
                "gender": request.gender.value,
                "existing_names": "",
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
        names = await self._check_duplicates(names, request.project_id)

        logger.info(
            "names_generated",
            name_type=request.name_type.value,
            culture=request.culture,
            count=len(names),
        )

        return NameGenerateResponse(
            names=names,
            count=len(names),
            culture=request.culture,
            name_type=request.name_type.value,
        )

    def _build_user_prompt(self, request: NameGenerateRequest) -> str:
        """Build the user-facing prompt for name generation."""
        return (
            f"Generate {request.count} {request.name_type.value} names "
            f"for a {request.culture} setting. "
            f"Gender preference: {request.gender.value}. "
            f"Language: {request.language}. "
            f"Return as JSON array with fields: name, pronunciation, meaning."
        )

    def _parse_names(self, text: str, request: NameGenerateRequest) -> list[GeneratedName]:
        """Parse LLM JSON response into GeneratedName objects.

        Args:
            text: Raw LLM response text.
            request: Original request for type/culture metadata.

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
                    culture=request.culture,
                ),
            )
        return names

    async def _check_duplicates(
        self,
        names: list[GeneratedName],
        project_id: UUID,
    ) -> list[GeneratedName]:
        """Check generated names against project KB for duplicates.

        TODO: Integrate with KB module once implemented.
        Currently returns all names with is_duplicate=False.
        """
        # Placeholder — KB module does not exist in API yet
        return names
