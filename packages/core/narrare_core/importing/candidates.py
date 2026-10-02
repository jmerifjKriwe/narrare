# packages/core/narrare_core/importing/candidates.py
"""Split-candidate discovery inside detected chapters (F1 — pure, I/O-free).

A split candidate is an ATX subheading (`###`..`######`) line inside a
DETECTED chapter's stored content (ADR-091 Amendment 2 / D2a). Chapter
content never contains `#`/`##` lines (the detector splits on those), so
level 3+ is the complete candidate set. Preview serializes
ordinal/heading/words_before; commit re-derives the identical capped list
and validates op ordinals against it — the deterministic re-parse contract
is preserved (``start`` stays Core-internal).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from narrare_core.importing.models import TITLE_MAX_LENGTH

#: ATX subheading line inside a chapter body: 3-6 '#' + whitespace + text.
ATX_SUBHEADING_RE = re.compile(r"^(#{3,6})\s+(.+?)\s*$", re.MULTILINE)

#: Deterministic per-chapter cap (D3a): a pathological chapter (5 MB of
#: `### x` lines) must not blow up the preview payload or validation cost.
#: The FIRST 200 candidates in document order are offered; ordinals are
#: assigned over the capped list, so ordinal >= 200 is unreachable.
SPLIT_CANDIDATES_MAX: Final[int] = 200


@dataclass(frozen=True, slots=True)
class SplitCandidate:
    """One `###`+ subheading usable as a split point.

    ``start``: char offset of the heading line inside the chapter content.
    ``words_before``: word count of the content strictly before this
    heading line — cumulative, so the frontend computes any part's word
    count exactly by subtraction (preview items carry no content).
    """

    ordinal: int
    heading: str
    start: int
    words_before: int


def find_split_candidates(content: str) -> list[SplitCandidate]:
    """Return the chapter's split candidates (capped, document order).

    Deterministic: identical content ⇒ identical list.
    """
    candidates: list[SplitCandidate] = []
    words_seen = 0
    cursor = 0
    for ordinal, match in enumerate(ATX_SUBHEADING_RE.finditer(content)):
        if ordinal == SPLIT_CANDIDATES_MAX:
            break
        # Words between the previous heading and this one (body prefix +
        # earlier heading lines) — counted incrementally, each char once.
        words_seen += len(content[cursor : match.start()].split())
        candidates.append(
            SplitCandidate(
                ordinal=ordinal,
                heading=match.group(2)[:TITLE_MAX_LENGTH],
                start=match.start(),
                words_before=words_seen,
            )
        )
        cursor = match.start()
    return candidates
