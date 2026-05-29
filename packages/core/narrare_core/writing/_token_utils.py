"""Lightweight token counting and budget capping utilities.

Extracted from ``budget.py`` for RULE-04 compliance.
Provides simple word-based token approximation and text truncation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


APPROX_TOKEN_FACTOR: float = 1.3
"""Multiplier applied to word count to approximate BPE token length."""


def default_token_counter(text: str) -> int:
    """Approximate token count: words * 1.3.

    Avoids a tiktoken dependency in core.  Consumers that need an
    accurate count (e.g. the API layer) can inject their own counter
    via the ``token_counter`` parameter of :func:`cap_to_budget`.
    """
    if not text:
        return 0
    return round(len(text.split()) * APPROX_TOKEN_FACTOR)


def cap_to_budget(
    text: str,
    max_tokens: int,
    token_counter: Callable[[str], int] | None = None,
) -> str:
    """Cap text to a token budget, truncating from the end if needed.

    Lightweight utility for services that need simple token enforcement
    without the full 5-tier allocation system.

    Args:
        text: The text to potentially truncate.
        max_tokens: Maximum allowed tokens.
        token_counter: Optional token counting function.
            Defaults to word-count * 1.3 approximation.

    Returns:
        Original text if within budget, otherwise truncated text.
        Returns empty string if *max_tokens* <= 0.
    """
    if max_tokens <= 0:
        return ""

    count = token_counter or default_token_counter

    if count(text) <= max_tokens:
        return text

    # Truncate at word boundaries by progressively removing trailing words.
    words = text.split()
    while words and count(" ".join(words)) > max_tokens:
        words.pop()

    return " ".join(words)
