"""Build the user-channel run prompt from selection text + mode.

RULE-02a: the selection text flows as category-3 runtime data (user
channel). It is NOT baked into the system prompt template. This helper
formats it for the agent run prompt when the composed prompt's user
channel is empty.

See:
    ADR-054 (Mode-1 PromptComposer),
    CONSTRAINTS.md RULE-02a (category 3 runtime data).
"""

from __future__ import annotations


def build_run_prompt(*, selection_text: str, mode: str, characters: list[str]) -> str:
    """Format the runtime user-channel prompt.

    Args:
        selection_text: The user's dialogue selection.
        mode: "analyze" or "improve".
        characters: Canonical speaker roster.

    Returns:
        A formatted prompt string for ``agent.run(prompt=...)``.
    """
    roster = ", ".join(characters) if characters else "(no attributed speakers)"
    return f"Mode: {mode}\nCharacters: {roster}\n\nDialogue to analyse:\n{selection_text}"
