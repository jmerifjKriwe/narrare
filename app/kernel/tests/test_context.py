"""The allocator's contract: token limits become named character budgets.

`allocate` is the one context path (WP2b design): pure, integer-exact, with
defaults that fall back independently (D7). These tests pin the arithmetic as
properties — the four slices sum exactly to the room, each small slice takes
its floor, the remainder lands in immediate text, a zero-room pair is
refused — and repeat the example numbers the E2E pins.
"""

import math
from dataclasses import astuple

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from app.kernel.context import (
    CHARS_PER_TOKEN,
    DEFAULT_CONTEXT_WINDOW,
    DEFAULT_MAX_OUTPUT_TOKENS,
    BudgetImpossibleError,
    ContextBudgets,
    allocate,
)

_LIMIT = st.integers(1, 200_000)


def _room(context_window: int, max_output_tokens: int) -> int:
    """The integer room the four slices share, as the design defines it."""
    return math.floor((context_window - max_output_tokens) * CHARS_PER_TOKEN)


@given(context_window=_LIMIT, max_output=_LIMIT)
def test_ordered_pair_slices_sum_exactly_to_the_room(context_window: int, max_output: int) -> None:
    """Four floors plus the remainder rebuild the room, slice by slice (60/25/10/5)."""
    assume(max_output < context_window)
    budgets = allocate(context_window=context_window, max_output_tokens=max_output)

    room = _room(context_window, max_output)
    assert (
        budgets.immediate_text
        + budgets.referenced_entities
        + budgets.recent_chapters
        + budgets.style_hints
        == room
    )
    assert min(astuple(budgets)) >= 0
    assert budgets.immediate_text >= math.floor(room * 0.60)
    assert budgets.referenced_entities == math.floor(room * 0.25)
    assert budgets.recent_chapters == math.floor(room * 0.10)
    assert budgets.style_hints == math.floor(room * 0.05)


@given(context_window=_LIMIT, max_output=_LIMIT)
def test_zero_room_pair_refused_naming_pair_and_model(context_window: int, max_output: int) -> None:
    """Equality and greater-than both refuse; the message names the pair and the model."""
    assume(max_output >= context_window)
    with pytest.raises(BudgetImpossibleError) as raised:
        allocate(
            context_window=context_window,
            max_output_tokens=max_output,
            model="test/model-1",
        )
    message = str(raised.value)
    assert str(context_window) in message
    assert str(max_output) in message
    assert "test/model-1" in message


def test_each_unset_limit_falls_back_to_its_default_alone() -> None:
    """D7: one unset limit does not drag the other to its default."""
    assert allocate(max_output_tokens=512) == allocate(
        context_window=DEFAULT_CONTEXT_WINDOW, max_output_tokens=512
    )
    assert allocate(context_window=4096) == allocate(
        context_window=4096, max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS
    )


def test_kernel_constants_pin_the_design_values() -> None:
    """The ratio is kernel-owned (D8); the defaults are the only fallbacks."""
    assert CHARS_PER_TOKEN == 3.5
    assert DEFAULT_CONTEXT_WINDOW == 8192
    assert DEFAULT_MAX_OUTPUT_TOKENS == 1024


@given(max_output=st.integers(1, 100_000))
def test_smallest_room_keeps_everything_in_immediate_text(max_output: int) -> None:
    """One token of room: the three small floors are zero and stay zero."""
    budgets = allocate(context_window=max_output + 1, max_output_tokens=max_output)
    assert budgets == ContextBudgets(
        immediate_text=3, referenced_entities=0, recent_chapters=0, style_hints=0
    )


def test_default_pair_yields_the_default_budgets() -> None:
    """(None, None) resolves to the defaults: room 25 088, remainder to immediate text."""
    assert allocate() == ContextBudgets(
        immediate_text=15054, referenced_entities=6272, recent_chapters=2508, style_hints=1254
    )


def test_e2e_pinned_pair_yields_the_pinned_budgets() -> None:
    """(2048, default output): room 3 584 → 2 151/896/358/179 — the E2E's numbers."""
    assert allocate(context_window=2048) == ContextBudgets(
        immediate_text=2151, referenced_entities=896, recent_chapters=358, style_hints=179
    )
