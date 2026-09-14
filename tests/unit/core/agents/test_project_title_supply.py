"""project_title supply chain for the WritingGraph — genre-mirror tests.

Defect: the review route's ``{{project_title}}`` rendered empty. The
supplier (``get_review_prompt``) read the assembled WritingContext's
metadata tier best-effort, but nothing populated it on graph paths:
the graph assembly seam omits the assembler's ``project_title``
parameter and ``WritingDeps`` carried no title field — unlike ``genre``
(pipeline context → ``WritingDeps.genre`` → ``_base_context``), the
title had no rail from the pipeline's assembled context to the render.

Fix (genre mirror, exactly): ``WritingDeps.project_title`` (default
``""``) is populated where deps are constructed from the assembled
``WritingContext`` (``pipeline_graph`` — stream and persistence paths),
``_base_context`` carries it plainly (template-owned labels render the
raw value, e.g. new_chapter's ``- Project: {{project_title}}`` line),
and the review supplier builds the label-in-value bullet with deps as
the primary source, the assembled WritingContext staying best-effort
fallback (data-fetching assemblers, ws_context_assembler precedent).

Empty degradation is unchanged (default ``""`` renders the bullet away
— pinned in test_review_prompt_word_target.py
TestReviewContextBulletsRender). All renders here compose through the
REAL ``PromptComposer`` + ``PromptRegistry`` (no composer mocks).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from narrare_core.agents.writing_graph_prompts import get_draft_prompt, get_review_prompt
from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.writing.models import WritingContext

_TITLE = "The Glass Archive"
_CH_ID = "550e8400-e29b-41d4-a716-446655440000"
_NOVEL_ID = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"


def _real_composer() -> PromptComposer:
    return PromptComposer(PromptRegistry())


def _deps(**overrides: Any) -> WritingDeps:
    defaults: dict[str, Any] = {
        "registry": AsyncMock(),
        "composer": _real_composer(),
        "genre": "Fantasy",
        "tone": "epic",
        "word_target": 2000,
        "writing_language": "English",
    }
    defaults.update(overrides)
    return WritingDeps(**defaults)


def _state(**overrides: Any) -> WritingState:
    defaults: dict[str, Any] = {"draft": "Elena crossed the flooded bridge at dawn."}
    defaults.update(overrides)
    return WritingState(**defaults)


class TestReviewRouteTitleRender:
    """deps.project_title renders as the full Project bullet exactly once."""

    async def test_deps_title_reaches_review_render_once(self) -> None:
        """Populated pin: the deps-supplied title (fetched from the owned
        novel at the API seam) renders the full bullet, in the former
        layout position (before the Genre bullet)."""
        system, _, _ = await get_review_prompt(
            composer=_real_composer(),
            deps=_deps(project_title=_TITLE),
            state=_state(),
        )
        assert system.count(f"- Project: {_TITLE}\n") == 1
        assert f"- Project: {_TITLE}\n- Genre: Fantasy" in system
        assert "{{" not in system, "placeholder residue in render"

    async def test_deps_title_precedes_assembled_title(self) -> None:
        """Deps is the primary source: when both deps and the assembled
        WritingContext carry a title, deps wins and the assembled value
        must not leak a second bullet."""
        assembler = AsyncMock()
        assembler.assemble = AsyncMock(
            return_value=WritingContext(project_title="Assembler-Supplied Title")
        )
        system, _, _ = await get_review_prompt(
            composer=_real_composer(),
            deps=_deps(project_title=_TITLE, context_assembler=assembler),
            state=_state(chapter_id=_CH_ID, novel_id=_NOVEL_ID),
        )
        assert system.count(f"- Project: {_TITLE}\n") == 1
        assert "Assembler-Supplied Title" not in system


class TestDraftRouteTitleRender:
    """The draft route renders the raw title via the template-owned label."""

    async def test_deps_title_reaches_draft_render_once(self) -> None:
        """Populated pin: the new_chapter template's static
        ``- Project: {{project_title}}`` line renders the deps-supplied
        title exactly once (plain value — no supplier bullet here)."""
        system, _ = await get_draft_prompt(
            composer=_real_composer(),
            deps=_deps(project_title=_TITLE),
            state=_state(),
        )
        assert system.count(f"- Project: {_TITLE}") == 1
        assert "{{" not in system, "placeholder residue in render"
