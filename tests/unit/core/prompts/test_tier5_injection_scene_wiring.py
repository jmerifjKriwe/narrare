"""Tier-5 KB injection — scene_by_scene pipeline-wiring tests.

Split from ``test_tier5_injection_scene.py`` per RULE-04 (R2-C1: the golden
recapture pushed the render-test module past the 400-line hard limit; the
wiring tests moved here so the render module keeps its golden + render pins).

Boundary
--------
These tests guard the PIPELINE WIRING only — that ``stream_scene_by_scene``
(via ``WritingPipeline.generate`` → ``_build_prompt_context``) forwards the
Tier-5 blocks, the ten ``kb_context_extras`` variables, and the fixed
``scene_by_scene`` route mode into the ``PromptContext`` it hands to the
composer. Render-level assertions (what the composed system prompt looks
like) live in ``test_tier5_injection_scene.py``.

Sentinel values duplicate the per-file convention of the other Tier-5
modules (``test_tier5_injection.py``, ``..._scene.py``, ``..._rewrite.py``,
``..._coauthor.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline

# Wire-format Tier-5 blocks exactly as T1a's ``_helpers.optional_block`` emits
# them (``"\n\n" + label + ":\n" + text``) — "" when the tier is empty.
_KB_SYSTEMS_BLOCK = "\n\nSystems:\nMagic costs stamina and cannot raise the dead."
_KB_TIMELINES_BLOCK = "\n\nTimelines:\nDay 1: The Fall of Thornwall."
_KB_PINNED_BLOCK = "\n\nPinned context (always included):\nNever kill Elena."

# A2 populated-delta sentinels: raw (render-ready) values for the five KB
# variables the scene route previously assembled but never supplied (they
# flow via WritingPipeline._build_prompt_context, not pipeline_scene.py).
_KB_RELATIONSHIPS_TEXT = "Elena and Mara: uneasy allies since the siege"
_KB_FACTIONS_TEXT = "### Faction: Bridge Wardens"
_KB_OTHER_TEXT = "### Item: Rusty Key"
_KB_SUGGESTED_TEXT = "### Character: Bernd (unaccepted candidate)"
_KB_CONTEXT_WARNINGS_TEXT = "Orphan reference: char-9 (removed entity)"


_CONFIG = ResolvedModelConfig(provider_name="test", model_id="test-model", max_tokens=2000)
_USAGE = TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)


async def _final_only_stream() -> AsyncIterator[StreamChunk]:
    yield StreamChunk(text="", is_final=True, usage=_USAGE)


class TestTier5SceneWiring:
    """scene_by_scene: the pipeline forwards Tier-5 + KB vars + route mode."""

    async def test_stream_scene_supplies_tier5_vars_in_extra(self) -> None:
        """stream_scene_by_scene forwards Tier-5 blocks + the fixed route mode.

        Guards the pipeline wiring (pipeline.py ``_build_prompt_context`` +
        the pipeline_scene.py route-composition fix): without the three keys,
        populated tiers would silently render "" via the route's
        optional-variable fallback (RULE-11); with the old ``mode="scene"``
        the real composition would raise PromptRouteNotConfiguredError.
        """
        composer = MagicMock(spec=PromptComposer)
        composer.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(
            return_value=WritingContext(
                project_title="Test Novel",
                genre="fantasy",
                language="en",
                tone="balanced",
                writing_language="English",
                chapter_outline="Single bridge scene outline.",
                word_target=400,
                kb_systems=_KB_SYSTEMS_BLOCK,
                kb_timelines=_KB_TIMELINES_BLOCK,
                kb_pinned=_KB_PINNED_BLOCK,
            )
        )
        registry = MagicMock(spec=["stream", "run"])
        registry.stream = MagicMock(spec=[], side_effect=lambda **kw: _final_only_stream())
        processor = MagicMock(spec=DraftProcessor)
        processor.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
        pipeline = WritingPipeline(
            registry=registry,
            composer=composer,
            context_assembler=assembler,
            draft_processor=processor,
        )
        request = GenerationRequest(
            chapter_id=uuid4(),
            project_id=uuid4(),
            user_id=uuid4(),
            mode=GenerationMode.SCENE_BY_SCENE,
            outline="Single bridge scene outline.",
        )

        async for _chunk in pipeline.generate(request, config=_CONFIG):
            pass

        prompt_ctx = composer.build.call_args.args[1]
        assert prompt_ctx.mode == "scene_by_scene"
        extra: dict[str, Any] = prompt_ctx.extra
        assert extra["kb_systems"] == _KB_SYSTEMS_BLOCK
        assert extra["kb_timelines"] == _KB_TIMELINES_BLOCK
        assert extra["kb_pinned"] == _KB_PINNED_BLOCK
        # Item-3: scene-position extras are forwarded (single-scene outline →
        # 1 of 1) and the redundant scene_outline extra is gone (the outline
        # flows as author_instructions; the var exists in no registry or
        # template — it was supplied-but-unrendered dead data).
        assert extra["scene_number"] == "1"
        assert extra["total_scenes"] == "1"
        assert "scene_outline" not in extra

    async def test_stream_scene_supplies_all_kb_vars_in_extra(self) -> None:
        """A2 wiring: the kb_context_extras merge forwards all ten KB vars.

        Without the merge in pipeline.py ``_build_prompt_context`` (which the
        scene route inherits), the five previously-unsupplied variables would
        silently render "" via the optional-variable fallback (RULE-11).
        """
        composer = MagicMock(spec=PromptComposer)
        composer.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(
            return_value=WritingContext(
                chapter_outline="Single bridge scene outline.",
                word_target=400,
                kb_relationships=_KB_RELATIONSHIPS_TEXT,
                kb_factions=_KB_FACTIONS_TEXT,
                kb_other=_KB_OTHER_TEXT,
                kb_suggested=_KB_SUGGESTED_TEXT,
                kb_context_warnings=_KB_CONTEXT_WARNINGS_TEXT,
            )
        )
        registry = MagicMock(spec=["stream", "run"])
        registry.stream = MagicMock(spec=[], side_effect=lambda **kw: _final_only_stream())
        processor = MagicMock(spec=DraftProcessor)
        processor.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
        pipeline = WritingPipeline(
            registry=registry,
            composer=composer,
            context_assembler=assembler,
            draft_processor=processor,
        )
        request = GenerationRequest(
            chapter_id=uuid4(),
            project_id=uuid4(),
            user_id=uuid4(),
            mode=GenerationMode.SCENE_BY_SCENE,
            outline="Single bridge scene outline.",
        )

        async for _chunk in pipeline.generate(request, config=_CONFIG):
            pass

        extra: dict[str, Any] = composer.build.call_args.args[1].extra
        assert extra["kb_relationships"] == _KB_RELATIONSHIPS_TEXT
        assert extra["kb_factions"] == _KB_FACTIONS_TEXT
        assert extra["kb_other"] == _KB_OTHER_TEXT
        assert extra["kb_suggested"] == _KB_SUGGESTED_TEXT
        assert extra["kb_context_warnings"] == _KB_CONTEXT_WARNINGS_TEXT
        # Previously-supplied variables keep identical values ("" here).
        assert extra["kb_characters"] == ""
        assert extra["kb_locations"] == ""
