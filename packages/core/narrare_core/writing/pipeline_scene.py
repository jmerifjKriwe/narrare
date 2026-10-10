"""Scene-by-scene generation mode.

Split from pipeline.py to respect RULE-04 (file size limit).
Generates a chapter one scene at a time, with ``***`` break markers
between scenes.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.planning.scene_render import render_scene_for_prompt
from narrare_core.shared.errors import WritingError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.writing.models import GenerationRequest, WritingContext
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)

# Pattern for splitting outlines into scenes
_NUMBERED_SCENE_RE = re.compile(r"(?m)^(\d+[.)]\s+)")


async def stream_scene_by_scene(
    pipeline: WritingPipeline,
    request: GenerationRequest,
    context: WritingContext,
    config: ResolvedModelConfig,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> AsyncIterator[StreamChunk]:
    """Generate chapter scene by scene with break markers."""
    if request.scenes:
        # Structured scene plans (PLAN-001 spec §8.1): render each spec
        # through the shared renderer — parse_scenes() is NOT used on this
        # path. len(scenes) == len(request.scenes) below.
        scenes = [
            render_scene_for_prompt(spec, number=idx) for idx, spec in enumerate(request.scenes, 1)
        ]
    else:
        scenes = parse_scenes(request.outline or context.chapter_outline)
    total_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

    for idx, scene_outline in enumerate(scenes, 1):
        if pipeline._is_stopped(request.id):  # pyright: ignore[reportPrivateUsage]
            break

        scene_prompt = pipeline._build_prompt_context(  # pyright: ignore[reportPrivateUsage]
            request,
            context,
            # Route-composition fix (T1f): "scene" is not a governed WRITE
            # context-mode (route_table.py); the governed mode is scene_by_scene.
            mode="scene_by_scene",
            author_instructions=scene_outline,
            extra_overrides={
                # Item-3: scene-position metadata rendered by the
                # scene_by_scene template numbering line. The scene outline
                # itself flows as author_instructions above — no separate
                # scene_outline extra (it was supplied-but-unrendered dead
                # data; the variable exists in no registry or template).
                "scene_number": str(idx),
                "total_scenes": str(len(scenes)),
            },
        )
        prompt = await pipeline._build_and_validate_prompt(  # pyright: ignore[reportPrivateUsage]
            LLMIntent.WRITE,
            scene_prompt,
            user_id=request.user_id,
            project_id=request.project_id,
        )

        accumulated: list[str] = []

        try:
            async for chunk in pipeline._registry.stream(  # pyright: ignore[reportPrivateUsage]
                intent=LLMIntent.WRITE,
                system_prompt=prompt.system,
                user_prompt=prompt.user,
                config=config,
                api_key=api_key,
                base_url=base_url,
            ):
                if pipeline._is_stopped(request.id):  # pyright: ignore[reportPrivateUsage]
                    break
                if chunk.is_final and chunk.usage:
                    total_usage = TokenUsage(
                        prompt_tokens=total_usage.prompt_tokens + chunk.usage.prompt_tokens,
                        completion_tokens=total_usage.completion_tokens
                        + chunk.usage.completion_tokens,
                        total_tokens=total_usage.total_tokens + chunk.usage.total_tokens,
                    )
                    continue
                accumulated.append(chunk.text)
                yield chunk

        except Exception as e:
            raise WritingError(
                f"Scene {idx} generation failed: {e}",
                code="SCENE_GENERATION_FAILED",
            ) from e

        if idx < len(scenes) and not pipeline._is_stopped(request.id):  # pyright: ignore[reportPrivateUsage]
            yield StreamChunk(text="\n\n***\n\n")

    yield StreamChunk(text="", is_final=True, usage=total_usage)


def parse_scenes(outline: str) -> list[str]:
    """Parse an outline into individual scene descriptions.

    Splits on ``***`` separators or numbered list markers.
    Falls back to treating the entire outline as one scene.
    """
    if not outline.strip():
        return [outline]

    # Split by *** separator
    if "***" in outline:
        scenes = [s.strip() for s in outline.split("***") if s.strip()]
        return scenes or [outline]

    # Split by numbered markers (e.g. "1. Scene description")
    parts = _NUMBERED_SCENE_RE.split(outline)
    if len(parts) > 1:
        scenes: list[str] = []
        for i in range(1, len(parts), 2):
            text = parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")
            text = text.strip()
            if text:
                scenes.append(text)
        return scenes or [outline]

    return [outline]
