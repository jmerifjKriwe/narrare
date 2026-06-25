"""StorySuggestAgent — NarrareAgent for story direction suggestions (Writer's Unblock).

Generates 3-5 distinct story suggestions (plot developments, character moments,
dialogue options, world details, stylistic alternatives) to help writers who
are stuck. Each suggestion explains how it connects to established plot threads.

Uses ``output_type=StorySuggestOutput`` — structured JSON output matching the
format declared in the ``story_suggest`` bundled template.

Usage:
    model = await registry.get_model(config)
    agent = StorySuggestAgent(model=model, system_prompt=composed.system)
    deps = StorySuggestDeps(
        project_title="The Last Kingdom",
        genre="Fantasy",
        writing_language="en",
    )
    result = await agent.run(
        prompt="I'm stuck after the protagonist enters the forest.",
        deps=deps,
    )
    for suggestion in result.suggestions:
        print(suggestion.title, suggestion.description)

See WRITE-009 (Writer's Unblock Tools).
"""

from __future__ import annotations

from typing import Any

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.story_suggest_types import StorySuggestDeps, StorySuggestOutput


class StorySuggestAgent(NarrareAgent[StorySuggestDeps, StorySuggestOutput]):
    """Agent for story direction suggestions (WRITE-009 Writer's Unblock).

    Generates 3-5 story suggestions (plot developments, character moments,
    dialogue options, etc.) to help writers who are stuck.

    System prompt is loaded from PromptComposer (RULE-02).
    The prompt key resolves to ``writing/{locale}/story_suggest/system.md``.
    """

    SYSTEM_PROMPT_KEY = "story_suggest"

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=StorySuggestDeps,
            output_type=StorySuggestOutput,
            system_prompt=system_prompt,
        )
