"""The language tag's grammar, width and fold — the one home every gate reads.

A BCP-47-ish tag: two or three lowercase letters, then optional subtags of one
to eight letters or digits after dashes (``de``, ``en-GB``, ``zh-Hans-CN``,
``de-CH-1906``). The width is the language columns' own and the registry's.
The registry, the novel update, the archive import and the settings payloads
read this module; none of them keeps a copy of the pattern or the number.

The fold is the update path's normalization, not a validity rule: the
surrounding whitespace drops, the primary subtag lowercases and the remainder
keeps the case it was typed in (``DE`` is ``de``, ``en-GB`` stays). Comparing
is done on the folded value, so a shouted primary subtag names the same
language; the stored archive value is never folded.
"""

import re

LANGUAGE_TAG = re.compile(r"[a-z]{2,3}(-[A-Za-z0-9]{1,8})*")
"""The compiled tag grammar; ``fullmatch`` is the membership test."""

LANGUAGE_TAG_MAX_LENGTH = 64
"""A tag's ceiling: the language columns' own width and the registry's."""


def fold_language_tag(value: str) -> str:
    """The update path's normalization: trimmed, primary subtag lowercased.

    The remainder keeps its case, so ``DE-CH-1906`` folds to ``de-CH-1906``
    and ``en-GB`` stays as it is.
    """
    primary, separator, remainder = value.strip().partition("-")
    return f"{primary.lower()}{separator}{remainder}"


def is_language_tag(value: str) -> bool:
    """True when the folded value is at most the width and matches the grammar."""
    folded = fold_language_tag(value)
    return len(folded) <= LANGUAGE_TAG_MAX_LENGTH and LANGUAGE_TAG.fullmatch(folded) is not None
