"""The one context allocator: a resolved profile's token limits become budgets.

`allocate` turns the resolved profile's `context_window` and `max_output_tokens`
into the four named character budgets a continuation fills — immediate text,
referenced entities, recent chapters, style hints, split 60/25/10/5 (D1: the
fractions live in this module and only here, overridable in code, never a
profile field). The budgets are derived in characters and are an estimate, not
a token guarantee: real token counts vary by tokenizer, model and content, so
the arithmetic keeps the margin implicit in 3.5 rather than claiming exact
token accounting (a provider-specific tokenizer is the trigger to revisit).

One integer rule: every slice takes its floor, the remainder goes to the
immediate-text slice, and a slice whose floor is zero stays zero — it is
omitted at assembly time, never given free space. The window arithmetic
refuses a zero-room pair: after the profile/catalog merge,
`max_output_tokens >= context_window` raises `BudgetImpossibleError` naming
the effective pair and the model — no clamp and no zero-input budget, because
a continuation with no input room is not a usable call.
"""

import math
from dataclasses import dataclass

CHARS_PER_TOKEN: float = 3.5
DEFAULT_CONTEXT_WINDOW = 8192
DEFAULT_MAX_OUTPUT_TOKENS = 1024

# The one split, in slice order; the remainder lands on the first entry.
_SLICE_FRACTIONS: tuple[tuple[str, float], ...] = (
    ("immediate_text", 0.60),
    ("referenced_entities", 0.25),
    ("recent_chapters", 0.10),
    ("style_hints", 0.05),
)


@dataclass(frozen=True)
class ContextBudgets:
    """The four named character budgets a continuation may fill."""

    immediate_text: int
    referenced_entities: int
    recent_chapters: int
    style_hints: int


class BudgetImpossibleError(ValueError):
    """The output reserve fills or exceeds the window: no usable continuation call."""


def allocate(
    *,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
    model: str | None = None,
) -> ContextBudgets:
    """Size the four continuation slices; pure, so the same inputs give the same budgets.

    Each unset limit falls back to its default independently (D7). After the
    defaults, `max_output_tokens >= context_window` refuses (D8, never clamped).
    """
    effective_window = DEFAULT_CONTEXT_WINDOW if context_window is None else context_window
    effective_output = DEFAULT_MAX_OUTPUT_TOKENS if max_output_tokens is None else max_output_tokens
    if effective_output >= effective_window:
        message = (
            f"no input room: max_output_tokens {effective_output} fills or exceeds"
            f" context_window {effective_window}"
        )
        if model is not None:
            message += f" for model {model}"
        raise BudgetImpossibleError(message + "; a continuation needs a positive input budget")

    room = math.floor((effective_window - effective_output) * CHARS_PER_TOKEN)
    floors = {name: math.floor(room * fraction) for name, fraction in _SLICE_FRACTIONS}
    return ContextBudgets(
        immediate_text=floors["immediate_text"] + (room - sum(floors.values())),
        referenced_entities=floors["referenced_entities"],
        recent_chapters=floors["recent_chapters"],
        style_hints=floors["style_hints"],
    )
