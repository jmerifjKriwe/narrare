"""The fake provider: deterministic prose, so the wire is testable end to end.

It is a catalog entry with the same interface as a real one, not a test branch:
routing, prompt composition, streaming and persistence run the same code
whichever name ``NARRE_LLM_PROVIDER`` selects.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator  # noqa: TC003
from typing import cast

from app.kernel.context import CHARS_PER_TOKEN
from app.kernel.contracts.models import ENTITY_TYPES
from app.kernel.llm.contract import (
    DONE,
    PURPOSE_INTERVIEW,
    PURPOSE_PREFIX,
    RELATIONS_PREFIX,
    REQUEST_PREFIX,
    ROSTER_PREFIX,
    SLOTS_PREFIX,
    SOURCE_PREFIX,
    TURNS_PREFIX,
    TYPE_PREFIX,
    USER_PREFIX,
    CompletionEvent,
    CompletionRequest,
    Delta,
    Usage,
)

PURPOSE_EXTRACT = "extract-entities"
PURPOSE_CHECK = "check-consistency"
# Kept in step with the job kinds whose prompts carry the purpose marker
# (knowledge's extraction and consistency checks) and with the interview's
# purpose. A purpose the fake does not know gets the default prose, whose
# shape the handler's parse refuses loudly — a drifted kind fails at its
# first job instead of silently. PURPOSE_INTERVIEW is imported: the constant
# belongs beside the markers because the template and its contract read it
# too.

PROPOSED_LIMIT = 8
# The answer's ceiling is the vocabulary it cycles: an extraction proposes
# min(distinct candidate names, 8) entities — one per type, in the
# vocabulary's order — so a chapter naming eight candidates yields the whole
# set. The type vocabulary is the extraction contract's own, imported from
# the kernel contracts (knowledge's prompt asks for exactly these); the
# handler's parse refuses anything else, so drift here fails loudly at the
# first extraction instead of silently.

RELATION_TYPE = "related_to"
# The fake's one relation type: entity i proposes this to entity i+1 (the
# last wraps to the first), so every derived answer names its links the way
# the contract now asks — deterministic, off the same names.

CAPITALIZED = re.compile(r"\b[ÄÖÜA-Z][äöüßa-z]+\b")

# A name paired with a number: the capitalized word, an optional lowercase
# connector word ("Mira ist 34"), then the number. The match is the reading
# as written, which a finding can quote.
WORD_NUMBER = re.compile(r"\b([ÄÖÜA-Z][äöüßa-z]+)(?:\s+[a-zäöüß]+)?\s+(\d+)\b")


def _purpose(prompt: str) -> str | None:
    """The purpose a marked prompt declares; None when no line carries it."""
    return _line_after(prompt, PURPOSE_PREFIX)


def _first_source(prompt: str) -> str | None:
    """Return the first source-marked line without its prefix, or None when absent."""
    for line in prompt.splitlines():
        if line.startswith(SOURCE_PREFIX):
            return line.removeprefix(SOURCE_PREFIX)
    return None


def _passages(prompt: str) -> list[str]:
    """Every passage behind a source marker, in order.

    A passage runs from its marker to the next one, not to the next line: a
    chapter body spans lines, so the marker names where a passage starts. A
    multi-passage prompt carries its later headings inside a passage — the
    fake is a stand-in that reads the marked text, not a prompt parser.
    """
    _, *passages = prompt.split(SOURCE_PREFIX)
    return passages


def _pieces(text: str) -> tuple[str, ...]:
    """Split into small pieces so the stream stays visible on the wire."""
    words = text.split()
    return tuple(
        " ".join(words[index : index + 4]) + (" " if index + 4 < len(words) else "")
        for index in range(0, len(words), 4)
    )


def _entities_answer(passage: str) -> str:
    """Deterministic extraction: the passage's capitalized words as entities.

    Names are derived from the prompt, so a test steers the fake with the
    chapter text alone: every distinct capitalized name the passage offers,
    to the vocabulary's ceiling of eight. Types cycle the extraction
    vocabulary in order of appearance, and each entity proposes one relation
    to its neighbor — entity i proposes ``related_to`` to entity i+1, the
    last wrapping to the first, so an answer with at least two entities
    names its links and a lone entity proposes none.
    """
    names = list(dict.fromkeys(CAPITALIZED.findall(passage)))[:PROPOSED_LIMIT]
    # The object root is the structured-outputs contract: an array is not a
    # legal root, so the ask and the answer share the {"items": [...]} shape.
    return json.dumps(
        {
            "items": [
                {
                    "name": name,
                    "type": ENTITY_TYPES[index % len(ENTITY_TYPES)],
                    "description": f"{name} appears in the chapter.",
                    "relations": (
                        [
                            {
                                "target": names[(index + 1) % len(names)],
                                "type": RELATION_TYPE,
                            }
                        ]
                        if len(names) >= 2
                        else []
                    ),
                }
                for index, name in enumerate(names)
            ]
        },
        ensure_ascii=False,
    )


def _findings_answer(text: str) -> str:
    """Deterministic consistency check: a name given two numbers contradicts itself.

    A real, small continuity check, not a fixture: the text's (name, number)
    pairs — a capitalized word with an optional connector and a number — are
    grouped by name, and a name carrying two distinct numbers is a
    contradiction: one finding that names the numbers and quotes both
    readings. A test steers the fake with the chapter texts alone.
    """
    # name -> number -> the first reading that carried the pair; dict order
    # keeps first appearance, so the answer is deterministic.
    readings: dict[str, dict[str, str]] = {}
    for match in WORD_NUMBER.finditer(text):
        name = match.group(1)
        number = match.group(2)
        readings.setdefault(name, {}).setdefault(number, match.group(0))
    findings: list[dict[str, str]] = []
    for name, by_number in readings.items():
        if len(by_number) < 2:
            continue
        numbers = list(by_number)
        findings.append(
            {
                "summary": f"{name}: {' vs. '.join(numbers)}",
                "detail": '"' + '" vs. "'.join(by_number.values()) + '"',
            }
        )
    # The object root is the structured-outputs contract (see the entities).
    return json.dumps({"items": findings}, ensure_ascii=False)


_INTERVIEW_SUGGESTION = "Ein Name, der zur Geschichte passt, wäre ein guter Anfang."
_INTERVIEW_NOTED = "Notiert."
_INTERVIEW_SUGGESTED = "Hier ist ein Vorschlag."
_INTERVIEW_FILLED = "Alles vorgeschlagen."

_FILL_NAME = "Unbenannt"
_FILL_ALIASES = ("Der Namenlose",)
_FILL_TAGS = ("neu",)
_FILL_CONTENT = "Ein Vorschlag des Fake-Treibers."
"""The canned values ``fill-all`` puts into every open slot — deterministic,
never derived from the story, because the fake stands in for a model."""


SECTION_HEADERS: tuple[str, ...] = (TURNS_PREFIX, ROSTER_PREFIX)
"""The lines that head a section body: the marker alone, nothing after it.

A roster entry can begin with ``ROSTER:`` — the name is user-derived — but never
amounts to the bare header, so an exact match is a section and nothing else.
"""

TOP_LEVEL_MARKERS: tuple[str, ...] = (
    PURPOSE_PREFIX,
    TYPE_PREFIX,
    SLOTS_PREFIX,
    RELATIONS_PREFIX,
    *SECTION_HEADERS,
    REQUEST_PREFIX,
)
"""The markers the template writes as lines of its own, outside every body."""


def _is_roster_entry(line: str) -> bool:
    """Whether a line has a roster line's shape: a name, then ``(type; aliases)``."""
    return line.rstrip().endswith(")") and " (" in line


def _section_bodies(lines: list[str]) -> dict[str, range]:
    """The line indices behind each section header, located independently.

    ``TURNS:`` and ``ROSTER:`` each head one body, and the interview's contract
    lets a re-voice render them in either order, so neither header is read off
    the other: the one that stands first is found first, whichever it is. A
    body runs from its own header line to the next line that is a top-level
    marker — a marker the template writes outside every body. Inside a body
    every line is an entry, whatever prefix it happens to start with: an entity
    named «ROSTER: X» or «REQUEST: fill-all» is one roster line, not a boundary
    and not a marker.

    A prompt without either header has no bodies, so a reader falls back to
    every line being a marker candidate (the chat and extraction shapes).
    """
    bodies: dict[str, range] = {}
    for header in SECTION_HEADERS:
        header_index = next(
            (index for index, line in enumerate(lines) if line.strip() == header), None
        )
        if header_index is None:
            continue
        end = len(lines)
        for index in range(header_index + 1, len(lines)):
            line = lines[index]
            if not line.strip() or line.strip() in SECTION_HEADERS:
                end = index
                break
            if not line.startswith(TOP_LEVEL_MARKERS):
                continue
            if header == ROSTER_PREFIX and _is_roster_entry(line):
                continue
            end = index
            break
        bodies[header] = range(header_index + 1, end)
    return bodies


def _line_after(prompt: str, prefix: str) -> str | None:
    """The value behind the first marker line outside the section bodies.

    The first occurrence outside ``TURNS:`` and ``ROSTER:`` is the template's
    own: each kernel-fed marker renders exactly once there, while a user-derived
    roster entry may begin with the same text. Inside a body every line is an
    entry, so a name that looks like a marker can never be read as one.
    """
    lines = prompt.splitlines()
    bodies = _section_bodies(lines)
    inside = {index for body in bodies.values() for index in body}
    for index, line in enumerate(lines):
        if index in inside:
            continue
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return None


def _json_line(prompt: str, prefix: str, default: object) -> object:
    """The JSON payload on a marked line, or ``default`` when absent or broken."""
    raw = _line_after(prompt, prefix)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _section_lines(prompt: str, header: str) -> list[str]:
    """The non-empty lines of a section body, in order.

    The body's extent comes from ``_section_bodies``, which finds the header
    wherever the re-voice placed it, so an entry starting with a marker prefix
    stays an entry; a blank line after the entries ends the block early, as the
    rendered roster has none.
    """
    lines = prompt.splitlines()
    body = _section_bodies(lines).get(header)
    if body is None:
        return []
    found: list[str] = []
    for line in (lines[index] for index in body):
        if not line.strip():
            if found:
                break
            continue
        found.append(line)
    return found


def _last_user_text(prompt: str) -> str:
    """The last ``USER:`` line of the turns body — the writer's latest turn.

    For an interview prompt the turns body is the transcript: when the prompt
    carries a ``TURNS:`` header, only that body is read, so a body that is
    missing or mis-scoped means no user turn at all instead of a ``USER:`` line
    found elsewhere in the frame. A prompt without the header falls back to an
    all-lines scan, which serves a headerless interview frame — a re-voiced
    prompt that dropped the ``TURNS:`` line. The other purposes' answers are
    unchanged because they never call this function.
    """
    lines = prompt.splitlines()
    body = _section_bodies(lines).get(TURNS_PREFIX)
    if body is not None:
        candidates = (lines[index] for index in body)
    elif any(line.strip() == TURNS_PREFIX for line in lines):
        candidates = iter(())
    else:
        candidates = iter(lines)
    text = ""
    for line in candidates:
        if line.startswith(USER_PREFIX):
            text = line.removeprefix(USER_PREFIX).strip()
    return text


def _split_labels(raw: str) -> list[str]:
    """Comma-separated labels, trimmed, blank entries dropped."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def _apply_interview_line(
    text: str, slots: dict[str, object], relations: list[dict[str, str]]
) -> None:
    """Apply the one recognized key line a writer's turn may carry."""
    if text.startswith("Name: "):
        slots["name"] = text.removeprefix("Name: ").strip()
    elif text.startswith("Beschreibung: "):
        slots["content"] = text.removeprefix("Beschreibung: ").strip()
    elif text.startswith("Schlagworte: "):
        slots["tags"] = _split_labels(text.removeprefix("Schlagworte: "))
    elif text.startswith("Alias: "):
        slots["aliases"] = _split_labels(text.removeprefix("Alias: "))
    elif text.startswith("Beziehung: "):
        target, _, label = text.removeprefix("Beziehung: ").partition("|")
        target, label = target.strip(), label.strip()
        if target and label:
            relations.append({"target": target, "type": label})


def _fill_open_slots(slots: dict[str, object]) -> None:
    """Fill every open slot with its canned value; closed slots keep what they hold."""
    if not slots.get("name"):
        slots["name"] = _FILL_NAME
    if not slots.get("aliases"):
        slots["aliases"] = list(_FILL_ALIASES)
    if not slots.get("tags"):
        slots["tags"] = list(_FILL_TAGS)
    if not slots.get("content"):
        slots["content"] = _FILL_CONTENT


def _interview_json(
    reply: str,
    slots: dict[str, object],
    relations: list[dict[str, str]],
    suggestion: str | None,
) -> str:
    """The interview's answer shape: the cumulative slots and the proposed relations."""
    answer: dict[str, object] = {"reply": reply, "slots": slots, "relations": relations}
    if suggestion is not None:
        answer["suggestion"] = suggestion
    return json.dumps(answer, ensure_ascii=False)


def _interview_answer(prompt: str) -> str:
    """The interview's deterministic turn, read from the marked lines.

    The answer is always the cumulative slots: the ones the prompt carried,
    updated by the writer's recognized key line or by ``fill-all``'s canned
    values. ``no-idea`` offers a suggestion and leaves the slots as received;
    ``fill-all`` also proposes one ``related_to`` to the first roster entry;
    ``accept-suggestion`` records the accepted text in ``content`` (set when
    empty, appended with a space otherwise); every other act acknowledges the
    turn. A last user turn of ``unparseable`` answers prose, so the structured
    ask's parse fails loudly instead of deriving a proposal from nothing.
    """
    parsed_slots = _json_line(prompt, SLOTS_PREFIX, {})
    slots = cast("dict[str, object]", parsed_slots) if isinstance(parsed_slots, dict) else {}
    parsed_relations = _json_line(prompt, RELATIONS_PREFIX, [])
    relations: list[dict[str, str]] = []
    if isinstance(parsed_relations, list):
        relations = [
            cast("dict[str, str]", relation)
            for relation in cast("list[object]", parsed_relations)
            if isinstance(relation, dict)
        ]

    user_text = _last_user_text(prompt)
    if user_text == "unparseable":
        return "".join(FakeProvider.CHUNKS)

    request = _line_after(prompt, REQUEST_PREFIX) or "answer"
    if request == "no-idea":
        return _interview_json(_INTERVIEW_SUGGESTED, slots, relations, _INTERVIEW_SUGGESTION)
    if request == "fill-all":
        _fill_open_slots(slots)
        roster = _section_lines(prompt, ROSTER_PREFIX)
        if roster:
            target = roster[0].split(" (", 1)[0].strip()
            if target and not any(relation.get("target") == target for relation in relations):
                relations.append({"target": target, "type": RELATION_TYPE})
        return _interview_json(_INTERVIEW_FILLED, slots, relations, None)
    if request == "accept-suggestion":
        content = slots.get("content")
        body = content if isinstance(content, str) and content else ""
        slots["content"] = f"{body} {user_text}".strip() if body else user_text
        return _interview_json(_INTERVIEW_NOTED, slots, relations, None)
    _apply_interview_line(user_text, slots, relations)
    return _interview_json(_INTERVIEW_NOTED, slots, relations, None)


class FakeProvider:
    """Deterministic prose, streamed in pieces, so the wire is visible end to end.

    Four shapes, because the pipeline has four. A prompt without a purpose
    marker keeps the chat behavior: a fixed continuation, or the first marked
    source quoted back (what lets a test see that retrieval reached the model
    boundary). A prompt that declares its purpose gets the answer that purpose
    contracts, derived from the marked lines: extraction proposes entities
    from its passage, the consistency check derives contradictions from every
    one of them, and the interview answers one turn from its marked slots and
    the writer's key line.
    """

    CHUNKS = (
        "Der Nebel hob sich ",
        "vom See und legte sich ",
        "über die Straße.",
    )

    def describe(self) -> str:
        """Identify the deterministic fake provider for startup logging."""
        return "fake"

    def configuration_problems(self) -> list[str]:
        """Report that the fake provider is ready without configuration."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Yield deterministic JSON for recognized extraction, check or interview purposes.

        Other prompts yield the first source line in pieces, or CHUNKS when
        that line is absent or empty. JSON answers arrive as a single piece.
        Only user-message contents, joined with newlines, form the prompt;
        other roles and completion options are ignored. Every shape ends with
        Usage, then DONE. Counts are deterministic: prompt and answer character
        lengths divided by the kernel's CHARS_PER_TOKEN, truncated to whole
        tokens — the same constant the allocator budgets with.
        """
        prompt = "\n".join(
            message.content for message in request.messages if message.role == "user"
        )
        purpose = _purpose(prompt)
        passages = _passages(prompt)
        if purpose == PURPOSE_EXTRACT:
            answer: str | None = _entities_answer("\n".join(passages).strip())
        elif purpose == PURPOSE_CHECK:
            answer = _findings_answer("\n".join(passages))
        elif purpose == PURPOSE_INTERVIEW:
            answer = _interview_answer(prompt)
        else:
            answer = None
        if answer is not None:
            # One piece is still a stream: the consumer sees the same protocol.
            await asyncio.sleep(0)
            yield Delta(text=answer)
            yield Usage(
                input_tokens=int(len(prompt) / CHARS_PER_TOKEN),
                output_tokens=int(len(answer) / CHARS_PER_TOKEN),
            )
            yield DONE
            return
        source = _first_source(prompt)
        chunks = _pieces(source) if source else self.CHUNKS
        for chunk in chunks:
            # Yield to the loop between pieces: the server flushes each event
            # instead of collapsing the whole completion into one write.
            await asyncio.sleep(0)
            yield Delta(text=chunk)
        answer_text = "".join(chunks)
        yield Usage(
            input_tokens=int(len(prompt) / CHARS_PER_TOKEN),
            output_tokens=int(len(answer_text) / CHARS_PER_TOKEN),
        )
        yield DONE
