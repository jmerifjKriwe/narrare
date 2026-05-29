"""InlineSuggestAgent — NarrareAgent for inline text suggestions (ghost text).

Generates short completions (1-3 sentences, max ~60 tokens) based on the
text immediately before the cursor.  Designed for low latency (<500ms target).

Uses ``output_type=str`` — plain text, no structured output parsing.
This avoids the overhead of tool-based output or JSON parsing.

Usage:
    model = await registry.get_model(config)
    agent = InlineSuggestAgent(model=model, system_prompt=composed.system)
    deps = InlineSuggestDeps(
        text_before="The hero walked into the dark forest,",
    )
    continuation = await agent.run(
        prompt="Continue this text.",
        deps=deps,
    )
    print(continuation)  # "his footsteps muffled by the thick carpet of fallen leaves."

See WRITE-007 (Inline AI Suggestions / Ghost Text).
"""

from __future__ import annotations

from typing import Any

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.inline_suggest_types import InlineSuggestDeps


class InlineSuggestAgent(NarrareAgent[InlineSuggestDeps, str]):
    """Agent for inline text suggestions (ghost text).

    Generates short completions (1-3 sentences, max ~60 tokens)
    based on the text immediately before the cursor.
    Designed for low latency (<500ms target).

    System prompt is loaded from PromptComposer (RULE-02).
    The prompt key resolves to ``writing/{locale}/inline_suggest/system.md``.
    """

    SYSTEM_PROMPT_KEY = "inline_suggest"

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=InlineSuggestDeps,
            output_type=str,
            system_prompt=system_prompt,
        )
