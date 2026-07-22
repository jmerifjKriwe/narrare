"""DialogueParser wrapper for selection-scoped speaker attribution.

ADR-069 Decision 7: reuse the established ADR-055 D3 pattern —
``DialogueParser.parse()`` extracts attributed utterances from the
selection text; the canonical speaker names feed the {{characters}}
template variable.

See:
    ADR-055 Decision 3 (DialogueParser + inline LLM resolution),
    ADR-069 Decision 7 (strict reuse),
    CONSTRAINTS.md RULE-04.
"""

from __future__ import annotations


def attribute_speakers(text: str) -> list[str]:
    """Return the sorted unique list of speakers found in *text*.

    Uses :class:`narrare_core.analysis.dialogue_parser.DialogueParser` —
    the deterministic ADR-055 D3 attribution. Speakers with ``None``
    confidence (no deterministic attribution) are omitted from the
    canonical roster; the LLM resolves them inline during the coach call.
    """
    if not text.strip():
        return []
    from narrare_core.analysis.dialogue_parser import DialogueParser

    parser = DialogueParser()
    utterances = parser.parse(text)
    speakers: set[str] = set()
    for u in utterances:
        if u.speaker:
            speakers.add(u.speaker)
    return sorted(speakers)
