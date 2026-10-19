"""DialogueParser — deterministic dialogue extraction + attribution (ANAL-008).

Splits chapter prose into dialogue utterances, then tag-attributes a speaker
to each quote where a deterministic signal exists (speech-verb tags,
action beats, em-dash attribution), with a confidence signal. Quotes with no
deterministic attribution resolve to ``speaker=None`` at low confidence and are
left for the LLM :class:`~narrare_core.agents.character_voice_agent.CharacterVoiceAgent`
to resolve inline (ADR-055 Decision 3 — self-contained hybrid, no Coreference
runtime coupling).

Layering (ADR-055 Risk #4 / RULE-07): raw quote-span *extraction* comes from
:func:`narrare_core.nlp.dialogue.extract_dialogue` (an ``nlp`` primitive);
this module owns *attribution + confidence* (analysis computation). The model
is pure — no I/O, no state — and never raises on malformed prose (RULE-11).
Identical input always yields identical output (ADR-021).

See Also
--------
ADR-021 — Deterministic analysis strategy.
ADR-055 — Character voice storage contract (Decision 3 attribution).
"""

from __future__ import annotations

import re

from narrare_core.analysis.voice_types import AttributedUtterance
from narrare_core.nlp.dialogue import extract_dialogue

# ---------------------------------------------------------------------------
# Confidence bands
# ---------------------------------------------------------------------------

#: Tag attribution via a speech verb (``"Hi," said Elena``).
CONFIDENCE_HIGH: float = 0.9
#: Action-beat / em-dash attribution (heuristic).
CONFIDENCE_MEDIUM: float = 0.6
#: No deterministic attribution found (left for the agent).
CONFIDENCE_LOW: float = 0.2

# ---------------------------------------------------------------------------
# Attribution patterns
# ---------------------------------------------------------------------------

# A proper-noun-ish name: one or two Capitalized words (first + last).
# Captured group 1 is the name.
_NAME_GROUP = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
_NAME_RE = re.compile(_NAME_GROUP)

# Speech verbs that introduce/finish a speaker tag.
_SPEECH_VERBS = (
    "said",
    "asked",
    "replied",
    "answered",
    "whispered",
    "shouted",
    "yelled",
    "murmured",
    "muttered",
    "screamed",
    "cried",
    "called",
    "breathed",
    "thought",
    "wondered",
    "continued",
    "added",
    "interrupted",
    "whined",
    "exclaimed",
    "snarled",
    "snapped",
    "hissed",
    "growled",
    "roared",
    "sobbed",
    "laughed",
    "chuckled",
    "whimpered",
    "rasped",
    "drawled",
    "echoed",
    "sang",
)
_VERB_ALT = "|".join(_SPEECH_VERBS)

# After a quote: "..." said Elena.  /  "..." Elena said.
_TAG_VERB_THEN_NAME = re.compile(rf"^\s*(?:{_VERB_ALT})\s+{_NAME_GROUP}\b")
_TAG_NAME_THEN_VERB = re.compile(rf"^\s*{_NAME_GROUP}\s+(?:{_VERB_ALT})\b")

# Before a quote: Elena said, "..."  /  said Elena, "..."
_PRE_NAME_THEN_VERB = re.compile(rf"{_NAME_GROUP}\s+(?:{_VERB_ALT})[\s,]*$")
_PRE_VERB_THEN_NAME = re.compile(rf"(?:{_VERB_ALT})\s+{_NAME_GROUP}[\s,]*$")

# Em-dash attribution right after the closing quote: "..." — Elena turned.
_EMDASH_THEN_NAME = re.compile(r"^\s*—\s*" + _NAME_GROUP + r"\b")

# Sentence boundary used to isolate the trailing action-beat clause.
_SENTENCE_SPLIT = re.compile(r"[.!?…]+\s+")

# Capitalized tokens that are almost never character names. Filtering these
# out prevents action-beat attribution from latching onto sentence-initial
# pronouns / articles / conjunctions (``The door opened. "Hi."`` → not "The").
_NON_NAMES = frozenset(
    {
        "he",
        "she",
        "it",
        "they",
        "we",
        "you",
        "i",
        "his",
        "her",
        "its",
        "their",
        "our",
        "my",
        "me",
        "him",
        "them",
        "us",
        "the",
        "this",
        "that",
        "these",
        "those",
        "there",
        "here",
        "but",
        "and",
        "or",
        "nor",
        "yet",
        "so",
        "for",
        "as",
        "if",
        "then",
        "when",
        "while",
        "where",
        "what",
        "why",
        "how",
        "who",
        "whom",
        "yes",
        "no",
        "not",
        "oh",
        "ah",
        "wow",
        "hey",
        "mr",
        "mrs",
        "ms",
        "dr",
        "sir",
        "maam",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "january",
        "february",
        "march",
        "april",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }
)


class DialogueParser:
    """Deterministic dialogue extraction + speaker attribution.

    All methods are pure — no state, no I/O. ``parse`` never raises on
    malformed prose (RULE-11): on any unexpected error it returns the
    utterances gathered so far (or an empty list).

    Args:
        context_window: How many characters of context around each quote
            to inspect for attribution signals. Defaults to
            :attr:`DEFAULT_CONTEXT_WINDOW`. Configurable per RULE-18
            (matches the :class:`~narrare_core.analysis.budget.AnalysisBudgetManager`
            pattern — class-level default + constructor injection).
    """

    #: Default context window (characters of surrounding prose to inspect).
    #: Class-level annotated constant + constructor parameter — the canonical
    #: RULE-18 pattern for configurable analyzer thresholds (cf.
    #: ``AnalysisBudgetManager.DEFAULT_TOTAL_BUDGET``).
    DEFAULT_CONTEXT_WINDOW: int = 160

    def __init__(self, context_window: int = DEFAULT_CONTEXT_WINDOW) -> None:
        self._context_window = context_window

    def parse(self, text: str) -> list[AttributedUtterance]:
        """Extract attributed dialogue utterances from *text*.

        Args:
            text: Prose text (chapter content, passage, etc.).

        Returns:
            Ordered :class:`AttributedUtterance` list. Quotes with no
            deterministic attribution have ``speaker=None``.
        """
        if not text or not text.strip():
            return []

        try:
            lines = extract_dialogue(text)
        except Exception:  # RULE-11: never crash on prose.
            return []

        utterances: list[AttributedUtterance] = []
        for line in lines:
            before = text[max(0, line.start - self._context_window) : line.start]
            after = text[line.end : min(len(text), line.end + self._context_window)]
            speaker, confidence = self._attribute(before, after)
            utterances.append(
                AttributedUtterance(
                    text=line.text,
                    speaker=speaker,
                    confidence=confidence,
                    start=line.start,
                    end=line.end,
                )
            )
        return utterances

    # ------------------------------------------------------------------
    # Attribution strategy (ordered: most → least confident)
    # ------------------------------------------------------------------

    @staticmethod
    def _attribute(before: str, after: str) -> tuple[str | None, float]:
        """Return ``(speaker, confidence)`` for a quote given its context.

        Tries, in order: speech-verb tag (after, then before) → action beat
        (before) → em-dash (after) → ``None`` at low confidence.
        """
        # 1. Speech-verb tag.
        name = DialogueParser._match_name(_TAG_VERB_THEN_NAME, after)
        if name is None:
            name = DialogueParser._match_name(_TAG_NAME_THEN_VERB, after)
        if name is None:
            name = DialogueParser._match_name(_PRE_NAME_THEN_VERB, before)
        if name is None:
            name = DialogueParser._match_name(_PRE_VERB_THEN_NAME, before)
        if name is not None:
            return name, CONFIDENCE_HIGH

        # 2. Action beat in the preceding clause.
        name = DialogueParser._action_beat_speaker(before)
        if name is not None:
            return name, CONFIDENCE_MEDIUM

        # 3. Em-dash attribution after the quote.
        name = DialogueParser._match_name(_EMDASH_THEN_NAME, after)
        if name is not None:
            return name, CONFIDENCE_MEDIUM

        # 4. No deterministic attribution.
        return None, CONFIDENCE_LOW

    @staticmethod
    def _match_name(pattern: re.Pattern[str], window: str) -> str | None:
        """Return the first plausible name captured by *pattern*, or ``None``."""
        match = pattern.search(window)
        if match is None:
            return None
        return DialogueParser._clean_name(match.group(1))

    @staticmethod
    def _action_beat_speaker(before: str) -> str | None:
        """Attribute to the last plausible name in the preceding clause.

        Considers only the trailing clause (after the last sentence boundary)
        so a name from an unrelated earlier sentence is not picked up. A speech
        verb anywhere in the clause suppresses attribution (the tag strategy
        should have handled that case).
        """
        if not before.strip():
            return None
        # Isolate the trailing clause.
        tail = _SENTENCE_SPLIT.split(before.strip())[-1]
        if not tail:
            return None
        if DialogueParser._contains_speech_verb(tail):
            return None
        candidates = [DialogueParser._clean_name(n) for n in _NAME_RE.findall(tail)]
        plausible = [c for c in candidates if c is not None]
        if not plausible:
            return None
        return plausible[-1]

    @staticmethod
    def _contains_speech_verb(text: str) -> bool:
        """True if *text* contains any known speech verb as a whole word."""
        return any(re.search(rf"\b{verb}\b", text) is not None for verb in _SPEECH_VERBS)

    @staticmethod
    def _clean_name(raw: str) -> str | None:
        """Filter out capitalized tokens that are not character names.

        Returns the trimmed name, or ``None`` when the first token is a known
        non-name (pronoun, article, day/month, interjection).
        """
        name = raw.strip()
        if not name:
            return None
        first = name.split()[0].lower().rstrip(".,;:!?")
        if first in _NON_NAMES:
            return None
        return name


# ---------------------------------------------------------------------------
# Roster-gated attribution (audit N11)
# ---------------------------------------------------------------------------


def restrict_speakers_to_roster(
    utterances: list[AttributedUtterance],
    roster: set[str],
) -> list[AttributedUtterance]:
    """Demote attributions whose speaker is not in the KB character roster.

    The action-beat heuristic accepts any capitalized token that is not in
    the finite ``_NON_NAMES`` list, so sentence-initial prose words ("In
    order to…") become MEDIUM-confidence "speakers" (audit N11: garbage
    characters in voice drift / check voice / character voices). The KB
    roster is the SSOT for who IS a character; a demoted utterance keeps
    its text/position with ``speaker=None`` at ``CONFIDENCE_LOW`` — the
    ADR-055 Decision 3 handoff: the agent resolves unattributed quotes
    inline (rendered ``?`` in the agent prompt).

    Empty *roster* → the input list unchanged (a KB-less novel has no SSOT
    to gate against; the parser's hint behavior stands). Inputs are never
    mutated — new utterances are returned for demotions.
    """
    if not roster:
        return utterances
    roster_cf = {name.casefold() for name in roster}
    gated: list[AttributedUtterance] = []
    for utt in utterances:
        if utt.speaker is not None and utt.speaker.casefold() not in roster_cf:
            gated.append(
                AttributedUtterance(
                    text=utt.text,
                    speaker=None,
                    confidence=CONFIDENCE_LOW,
                    start=utt.start,
                    end=utt.end,
                )
            )
        else:
            gated.append(utt)
    return gated


def filter_speaker_names(names: set[str], roster: set[str]) -> set[str]:
    """Name-set form of :func:`restrict_speakers_to_roster` (drift seam)."""
    if not roster:
        return set(names)
    roster_cf = {name.casefold() for name in roster}
    return {name for name in names if name.casefold() in roster_cf}
