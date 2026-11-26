"""The interview's behaviour between storage and prompt: five reads and a turn.

A turn runs in three steps and never holds a transaction across the model call.
A short read hands back the session, its proposal and the newest turns, and
ends. The prompt renders and the provider resolves; that transaction ends too.
Then one transaction takes the session's lock, allocates the two turns' ``seq``,
merges the model's changes into the proposal as it stands under the lock and
writes the audit rows. A failed turn writes its collected audit rows alone, in
one short transaction, before the named refusal.

The proposal is merged, not replaced: the model's answer is compared with the
proposal it was given, and only what it changed is written; untouched parts
come from the locked proposal, so a concurrent turn's fields survive. The
provenance is the server's, read from the act: new after ``fill-all`` is
suggested, new or changed after any other act is the writer's own, unchanged
keeps its mark.
"""

import json
from collections.abc import AsyncIterator, Mapping  # noqa: TC003  signatures evaluate
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING, Final, cast
from uuid import UUID  # noqa: TC003  signatures and the dataclass evaluate

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002  the service's field

from app.capabilities.chat.models import AssistantSession, AssistantTurn  # noqa: TC001
from app.capabilities.chat.prompts import (
    CHAT_KEY,
    INTERVIEW_KEY,
    ROSTER_LIMIT,
    novel_variables,
    roster_for_prompt,
    turn_line,
)
from app.capabilities.chat.repository import (
    AssistantSessionRepository,
    EntityRosterRepository,
    NovelRepository,
    SessionListRow,
)
from app.capabilities.chat.schemas import (
    Proposal,
    SessionCreate,
    TurnCreate,
    TurnReadback,
)
from app.kernel.contracts.models import ENTITY_TYPES, MAX_RELATIONS, Entity
from app.kernel.errors import ErrorCode
from app.kernel.llm import (
    ASSISTANT_PREFIX,
    USER_PREFIX,
    AuditedCall,
    MalformedAnswerError,
    TextProvider,
    ask_structured,
    single_line,
)
from app.kernel.llm.audit import record_call
from app.kernel.llm.resolution import ResolvedProvider, resolve_provider
from app.kernel.prompts import PromptRenderError, render

if TYPE_CHECKING:
    from app.kernel.llm.contract import CompletionEvent, CompletionRequest

MODE_KNOWLEDGE_ENTITY: Final = "knowledge.entity"
"""The one mode cut 1 carries; the vocabulary is checked at the request boundary."""

MODEL_ACTS: Final[frozenset[str | None]] = frozenset(
    {None, "accept-suggestion", "no-idea", "fill-all"}
)
"""The acts that call the model: a plain turn and the three model answers."""

TRANSCRIPT_LIMIT: Final = 20
"""How many conversation turns the model sees, the writer's current one included."""

TRANSCRIPT_READ_LIMIT: Final = 10_000
"""The most turns the detail and the suggestion search read: far past any real
session, so nothing a writer can reach is hidden."""

NAME_LIMIT: Final = 200
"""The longest name, alias, tag or relation target the dialog stores."""

RELATION_TYPE_LIMIT: Final = 80
"""The longest relation type, as the creation endpoint will also bound it."""

CONTENT_LIMIT: Final = 10_000
"""The longest proposal body."""

SLOT_KEYS: Final = ("name", "aliases", "tags", "content")
LABEL_KEYS: Final = ("aliases", "tags")

INTERVIEW_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "slots": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "aliases": {"type": "array", "items": {"type": "string"}},
                "tags": {"type": "array", "items": {"type": "string"}},
                "content": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "type": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["target", "type"],
                "additionalProperties": False,
            },
        },
        "suggestion": {"type": "string"},
    },
    "required": ["reply", "slots"],
    "additionalProperties": False,
}
"""The one shape the answer must carry; the parse below checks the same fields."""


class InterviewRefusalError(Exception):
    """A refusal the router writes as ``{"detail": {"code": …, "detail": …}}``."""

    status: int = 400
    code: ErrorCode


class InterviewNotFoundError(InterviewRefusalError):
    """The session or novel is absent, or another user's: one indistinguishable answer."""

    status = 404
    code = ErrorCode.NOT_FOUND


class SessionClosedError(InterviewRefusalError):
    """The interview was ended; its transcript is read-only."""

    status = 409
    code = ErrorCode.SESSION_CLOSED


class InterviewValidationError(InterviewRefusalError):
    """A body outside the mode's contract, with the reason's own code."""

    status = 422

    def __init__(self, code: ErrorCode, detail: str) -> None:
        self.code = code
        super().__init__(detail)


class ExtractionFailedError(InterviewRefusalError):
    """Twice-unreadable model answer; nothing was written."""

    status = 502
    code = ErrorCode.EXTRACTION_FAILED


class ProviderUnavailableError(InterviewRefusalError):
    """No serving tier answered for ``chat.ask``; the cascade's reason rides along."""

    status = 502
    code = ErrorCode.PROVIDER_UNAVAILABLE


class ProviderCallError(InterviewRefusalError):
    """The provider call died; the class is named so the reader knows what failed."""

    status = 502
    code = ErrorCode.PROVIDER_ERROR


class PromptRefusedError(InterviewRefusalError):
    """The interview prompt's effective source no longer renders."""

    status = 502
    code = ErrorCode.PROMPT_REFUSED


@dataclass(frozen=True)
class InterviewAnswer:
    """What the model answered, still unnormalised: the parse's typed result.

    ``relations`` is ``None`` when the answer left the key out — untouched —
    and a list, empty included, when it gave one: the list is the answer's
    changes to the relations it was shown.
    """

    reply: str
    slots: dict[str, object]
    relations: list[dict[str, str]] | None
    suggestion: str | None


class _PromptRecorder:
    """The provider view that remembers the prompt of the attempt in flight.

    ``ask_structured`` audits a call only after it returns; a provider that
    raises never reaches that callback, so the failure's own row needs the
    prompt of the attempt that died. Recording the request before delegating
    keeps that row exact, the retry correction included.
    """

    def __init__(self, provider: TextProvider) -> None:
        self.provider = provider
        self.prompt = ""
        self.latency_ms = 0

    def describe(self) -> str:
        """The wrapped provider's one-line description."""
        return self.provider.describe()

    def configuration_problems(self) -> list[str]:
        """The wrapped provider's readiness."""
        return self.provider.configuration_problems()

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Record the request and its elapsed time, then yield the provider's events."""
        self.prompt = "\n".join(message.content for message in request.messages)
        started = monotonic()
        try:
            async for event in self.provider.stream(request):
                yield event
        finally:
            self.latency_ms = round((monotonic() - started) * 1000)


@dataclass(frozen=True)
class _TurnState:
    """The short read's result, held as values after its transaction ends.

    The ORM objects are detached here on purpose: step 3 loads the session
    again under the lock, and a stale identity-mapped row would hide the
    concurrent turn the merge exists for.
    """

    session_id: UUID
    novel_id: UUID
    entity_type: str
    proposal: dict[str, object] | None
    closed: bool
    turns: list[AssistantTurn]
    heading: tuple[str, str | None]
    roster: list[Entity]
    roster_cut: bool


def _text(value: object) -> str:
    """A JSON value read as text; anything but a string is the empty text."""
    return value if isinstance(value, str) else ""


def _parse_answer(answer: str) -> InterviewAnswer:
    """Read the contracted answer; a refusal names what to fix for the retry."""
    try:
        data = cast("object", json.loads(answer))
    except ValueError as error:
        raise ValueError("the answer is not JSON") from error
    if not isinstance(data, dict):
        raise ValueError("the answer is not a JSON object")
    record = cast("dict[str, object]", data)

    reply = record.get("reply")
    if not isinstance(reply, str):
        raise ValueError("the answer carries no reply sentence")

    raw_slots = record.get("slots", {})
    if not isinstance(raw_slots, dict):
        raise ValueError("the answer's slots are not a JSON object")
    slot_record = cast("dict[str, object]", raw_slots)
    slots: dict[str, object] = {}
    # A slot key's PRESENCE is the contract's first state: a key left out is
    # untouched, while a key given empty — "" or null for name and content,
    # [] for aliases and tags — asks for the clear. So both the key and its
    # empty form are kept here; only an absent key stays absent.
    for key in ("name", "content"):
        if key not in slot_record:
            continue
        value = slot_record[key]
        if value is None:
            slots[key] = ""
            continue
        if not isinstance(value, str):
            raise ValueError(f"the answer's {key} is not a string")
        slots[key] = value
    for key in LABEL_KEYS:
        if key not in slot_record:
            continue
        labels = slot_record[key]
        if labels is None:
            # A null list is no list: the contract names [] as the clear, so
            # a null leaves the slot untouched rather than guessing a meaning.
            continue
        if not isinstance(labels, list):
            raise ValueError(f"the answer's {key} are not a JSON array")
        cleaned: list[str] = []
        for label in cast("list[object]", labels):
            if not isinstance(label, str):
                raise ValueError(f"the answer's {key} are not strings")
            cleaned.append(label)
        slots[key] = cleaned

    relations: list[dict[str, str]] | None = None
    raw_relations = record.get("relations")
    if raw_relations is not None:
        if not isinstance(raw_relations, list):
            raise ValueError("the answer's relations are not a JSON array")
        relations = []
        for entry in cast("list[object]", raw_relations):
            if not isinstance(entry, dict):
                raise ValueError("a relation is not a JSON object")
            relation = cast("dict[str, object]", entry)
            target = relation.get("target")
            type_ = relation.get("type")
            note = relation.get("note")
            if not isinstance(target, str) or not target.strip():
                raise ValueError("a relation carries no target")
            if not isinstance(type_, str) or not type_.strip():
                raise ValueError("a relation carries no type")
            if note is not None and not isinstance(note, str):
                raise ValueError("a relation's note is not a string")
            relations.append({"target": target, "type": type_, "note": note or ""})

    suggestion = record.get("suggestion")
    if suggestion is not None and not isinstance(suggestion, str):
        raise ValueError("the answer's suggestion is not a string")
    return InterviewAnswer(reply=reply, slots=slots, relations=relations, suggestion=suggestion)


def _one_line(value: str, limit: int) -> str:
    """One stored string: a single line, cut to its limit."""
    return single_line(value)[:limit]


def _labels(values: list[str]) -> list[str]:
    """Aliases or tags: non-blank, one line, cut, case-insensitively deduplicated."""
    seen: set[str] = set()
    kept: list[str] = []
    for value in values:
        label = _one_line(value, NAME_LIMIT)
        key = label.casefold()
        if not label or key in seen:
            continue
        seen.add(key)
        kept.append(label)
    return kept


def _normalise_slots(slots: dict[str, object]) -> dict[str, object]:
    """The answer's slots after normalisation, each present key kept.

    Presence is the answer's own signal: a key the answer did not give is
    absent here too, while a key it gave empty stays — ``""`` for name and
    content, ``[]`` for a list whose entries were all blank — so the merge can
    apply the clear instead of losing it.
    """
    cleaned: dict[str, object] = {}
    if "name" in slots:
        name = slots["name"]
        cleaned["name"] = _one_line(name, NAME_LIMIT) if isinstance(name, str) else ""
    for key in LABEL_KEYS:
        if key in slots:
            values = slots[key]
            cleaned[key] = _labels(cast("list[str]", values)) if isinstance(values, list) else []
    if "content" in slots:
        content = slots["content"]
        cleaned["content"] = _one_line(content, CONTENT_LIMIT) if isinstance(content, str) else ""
    return cleaned


def _normalise_relations(relations: list[dict[str, str]]) -> list[dict[str, str]]:
    """The answer's relations: non-blank, bounded, at most ``MAX_RELATIONS``."""
    kept: list[dict[str, str]] = []
    for relation in relations:
        target = _one_line(relation["target"], NAME_LIMIT)
        type_ = _one_line(relation["type"], RELATION_TYPE_LIMIT)
        if not target or not type_:
            continue
        kept.append({"target": target, "type": type_, "note": single_line(relation["note"])})
        if len(kept) == MAX_RELATIONS:
            break
    return kept


def _proposal_slots(proposal: dict[str, object] | None) -> dict[str, object]:
    """The proposal's non-empty slot values, without the provenance marks."""
    if not proposal:
        return {}
    slots: dict[str, object] = {}
    for key in SLOT_KEYS:
        value = proposal.get(key)
        if value:
            slots[key] = value
    return slots


def _proposal_relations(
    proposal: dict[str, object] | None,
) -> list[dict[str, object]]:
    """The proposal's relation rows, provenance included, as stored."""
    if not proposal:
        return []
    raw = proposal.get("relations")
    if not isinstance(raw, list):
        return []
    return [
        cast("dict[str, object]", entry)
        for entry in cast("list[object]", raw)
        if isinstance(entry, dict)
    ]


def _text_list(value: object) -> list[str]:
    """A list slot's items as strings; anything else is the empty list."""
    if not isinstance(value, list):
        return []
    return [item for item in cast("list[object]", value) if isinstance(item, str)]


def _suggested_map(proposal: dict[str, object] | None) -> dict[str, object]:
    """Which parts the proposal marks suggested: item values for lists, a flag for content."""
    marks: dict[str, object] = {"aliases": [], "tags": [], "content": False}
    if not proposal:
        return marks
    raw = proposal.get("suggested")
    if not isinstance(raw, dict):
        return marks
    record = cast("dict[str, object]", raw)
    for key in LABEL_KEYS:
        stored = record.get(key)
        if isinstance(stored, list):
            marks[key] = _text_list(cast("object", stored))
    marks["content"] = bool(record.get("content"))
    return marks


def _merge_labels(
    now_items: list[str],
    now_marks: list[str],
    given_items: list[str],
    answer_items: list[str],
    act: str | None,
) -> tuple[list[str], list[str]]:
    """Merge the answer's list into the locked list, item by item.

    The locked list keeps every item; the answer's list is read as its changes
    to its input. An item the answer dropped that its input carried leaves; an
    item it added joins. An item the answer restates — its input carried it,
    whatever its case — is neither appended nor re-marked: whether it still
    exists is the locked proposal's to say, so one another turn removed stays
    removed. A restatement that differs only in case keeps the locked spelling.
    The marks follow: an unchanged item keeps the mark the locked proposal gave
    it, a new or changed one is suggested under ``fill-all`` and the writer's
    own after any other act.
    """
    given_by_key = {item.casefold(): item for item in given_items}
    answer_by_key = {item.casefold(): item for item in answer_items}
    merged: list[str] = []
    positions: dict[str, int] = {}
    for item in now_items:
        key = item.casefold()
        if key in given_by_key and key not in answer_by_key:
            continue
        if key in positions:
            continue
        positions[key] = len(merged)
        merged.append(item)
    now_by_key = {item.casefold(): item for item in now_items}
    for item in answer_items:
        key = item.casefold()
        # A restatement is not the answer's change: it neither resurrects an
        # item the locked proposal lost nor re-marks one still there.
        if key in positions or key in given_by_key:
            continue
        positions[key] = len(merged)
        merged.append(item)
    marked_keys = {item.casefold() for item in now_marks}
    marks: list[str] = []
    for item in merged:
        # Identity is case-insensitive here as everywhere else: a restatement
        # that differs only in case is the locked item, so it keeps its mark.
        key = item.casefold()
        locked = now_by_key.get(key)
        suggested = act == "fill-all" if locked is None else key in marked_keys
        if suggested:
            marks.append(item)
    return merged, marks


def _relation_key(relation: Mapping[str, object]) -> tuple[str, str, str]:
    """A relation's unchanged identity for the merge: its target, type and note."""
    return (
        _text(relation.get("target")).strip().casefold(),
        _text(relation.get("type")),
        _text(relation.get("note")),
    )


def _relation_position(relation: Mapping[str, object]) -> tuple[str, str]:
    """A relation's identity for the merge: its target and type; the note is a field."""
    return (_text(relation.get("target")).strip().casefold(), _text(relation.get("type")))


def _merge_relations(
    now: list[dict[str, object]],
    given: list[dict[str, object]],
    model: list[dict[str, str]],
    act: str | None,
) -> list[dict[str, object]]:
    """Merge the answer's relations into the locked proposal, relation by relation.

    The answer's list is read as its changes to its input: the locked proposal
    keeps every relation, loses only one the answer dropped that its input
    carried, and takes a changed or new one in place — keyed by target and
    type, so two relations to one target survive with their own types. A
    relation the answer carried unchanged is left to the locked proposal; a new
    or changed one takes its provenance from the act.

    The merged set is bounded like an answer: the entries the answer was not
    shown (the locked proposal's, in their order) stand first, and only as many
    of the answer's additions as fit join them — a new one beyond
    ``MAX_RELATIONS`` is not added, so two answers computed against the same
    older proposal cannot carry the set past the bound.
    """
    given_positions = {_relation_position(relation) for relation in given}
    answer_positions = {_relation_position(relation) for relation in model}
    merged: list[dict[str, object]] = []
    positions: dict[tuple[str, str], int] = {}
    for relation in now:
        position = _relation_position(relation)
        if position in given_positions and position not in answer_positions:
            continue
        if position in positions:
            continue
        positions[position] = len(merged)
        merged.append(dict(relation))
    unchanged = {_relation_key(relation) for relation in given}
    for relation in model:
        if _relation_key(relation) in unchanged:
            continue
        stored: dict[str, object] = {
            "target": relation["target"],
            "type": relation["type"],
            "note": relation["note"],
            "suggested": act == "fill-all",
        }
        position = _relation_position(relation)
        index = positions.get(position)
        if index is None:
            positions[position] = len(merged)
            merged.append(stored)
        else:
            merged[index] = stored
    # The bound holds on the merged set too, not only on one answer: the
    # locked entries the answer was not shown stand first, so the cut can only
    # drop the answer's additions beyond what twelve leave room for.
    return merged[:MAX_RELATIONS]


def _merge_proposal(
    now: dict[str, object] | None,
    given: dict[str, object] | None,
    answer: InterviewAnswer,
    act: str | None,
) -> dict[str, object] | None:
    """The locked proposal with the answer's changes, and only its changes.

    A merged proposal with nothing in it — no name, aliases, tags, content or
    relation — is ``None``: a turn that changed nothing leaves the session's
    ``proposal`` as empty as it found it, not an empty object.
    """
    given_slots = _proposal_slots(given)
    slots = dict(_proposal_slots(now))
    suggested = _suggested_map(now)
    name_suggested = bool(now.get("name_suggested")) if now else False
    for key, value in _normalise_slots(answer.slots).items():
        if key in LABEL_KEYS:
            merged_items, merged_marks = _merge_labels(
                _text_list(slots.get(key)),
                cast("list[str]", suggested[key]),
                _text_list(given_slots.get(key)),
                cast("list[str]", value),
                act,
            )
            if merged_items:
                slots[key] = merged_items
            else:
                slots.pop(key, None)
            suggested[key] = merged_marks
            continue
        if value == (given_slots.get(key) or ""):
            # Unchanged relative to its input — including empty both ways — so
            # the locked value stands, with its mark, even when another turn
            # wrote it while the model answered.
            continue
        if not value:
            # The third state: the answer gave the key empty while its input
            # carried a value, so it changed it — the slot is cleared and its
            # mark with it. A list path above reaches the same result through
            # the union: an empty list drops what it was given.
            slots.pop(key, None)
            if key == "name":
                name_suggested = False
            else:
                suggested[key] = False
            continue
        if key == "name":
            name_suggested = act == "fill-all"
        else:
            suggested[key] = act == "fill-all"
        slots[key] = value
    relations = (
        _merge_relations(
            _proposal_relations(now),
            _proposal_relations(given),
            _normalise_relations(answer.relations),
            act,
        )
        if answer.relations is not None
        else _proposal_relations(now)
    )
    name = _text(slots.get("name"))
    aliases = _text_list(slots.get("aliases"))
    tags = _text_list(slots.get("tags"))
    content = _text(slots.get("content"))
    if not name and not aliases and not tags and not content and not relations:
        return None
    return {
        "name": name or None,
        "name_suggested": name_suggested and bool(name),
        "aliases": aliases,
        "tags": tags,
        "content": content,
        "suggested": suggested,
        "relations": relations,
    }


def _drop_suggested(
    proposal: dict[str, object] | None,
) -> dict[str, object] | None:
    """The proposal without any suggested part; what the writer said stays.

    A proposal with nothing left after the drop — no name, aliases, tags, content
    or relation — is ``None``, as an empty merge is.
    """
    if proposal is None:
        return None
    slots = _proposal_slots(proposal)
    suggested = _suggested_map(proposal)
    if bool(proposal.get("name_suggested")):
        slots.pop("name", None)
    for key in LABEL_KEYS:
        marked = {item.casefold() for item in cast("list[str]", suggested[key])}
        kept = [item for item in _text_list(slots.get(key)) if item.casefold() not in marked]
        if kept:
            slots[key] = kept
        else:
            slots.pop(key, None)
    if bool(suggested["content"]):
        slots.pop("content", None)
    relations = [
        dict(relation)
        for relation in _proposal_relations(proposal)
        if not bool(relation.get("suggested"))
    ]
    for relation in relations:
        relation["suggested"] = False
    name = _text(slots.get("name"))
    aliases = _text_list(slots.get("aliases"))
    tags = _text_list(slots.get("tags"))
    content = _text(slots.get("content"))
    if not name and not aliases and not tags and not content and not relations:
        return None
    return {
        "name": name or None,
        "name_suggested": False,
        "aliases": aliases,
        "tags": tags,
        "content": content,
        "suggested": {"aliases": [], "tags": [], "content": False},
        "relations": relations,
    }


def _read_proposal(proposal: dict[str, object] | None) -> Proposal | None:
    """The stored proposal as the wire reads it."""
    return Proposal.model_validate(proposal) if proposal is not None else None


def _pending(turns: list[AssistantTurn]) -> AssistantTurn | None:
    """The newest assistant turn whose suggestion is still pending, if any."""
    for turn in reversed(turns):
        if turn.suggestion_state == "pending":
            return turn
    return None


def _accepted_text(text: str, settled: str | None) -> str:
    """An accepted suggestion's text, or the coded refusal when the client's differs.

    The server owns the answer: the settled suggestion's own text is stored as
    the writer's turn, so a client cannot put words in the writer's mouth. An
    empty ``text`` takes the suggestion; anything else must equal it.
    """
    if not settled:
        raise InterviewValidationError(
            ErrorCode.SUGGESTION_MISMATCH, "there is no pending suggestion to accept"
        )
    if text and text != settled:
        raise InterviewValidationError(
            ErrorCode.SUGGESTION_MISMATCH, "the text is not the pending suggestion"
        )
    return settled


def _failure_name(error: Exception) -> str:
    """The provider error's class, with its message when it carries one."""
    message = str(error)
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


def _relations_for_prompt(proposal: dict[str, object] | None) -> list[dict[str, str]]:
    """The proposal's relations as the model reads them, without provenance."""
    return [
        {
            "target": _text(relation.get("target")),
            "type": _text(relation.get("type")),
            "note": _text(relation.get("note")),
        }
        for relation in _proposal_relations(proposal)
    ]


class InterviewService:
    """One user's interviews: open, list, read, take a turn, close."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.sessions = AssistantSessionRepository(session, user_id)
        self.roster = EntityRosterRepository(session, user_id)
        self.novels = NovelRepository(session, user_id)

    async def open_session(self, payload: SessionCreate) -> AssistantSession:
        """Open an interview after checking the mode, its type and the novel."""
        if payload.mode != MODE_KNOWLEDGE_ENTITY:
            raise InterviewValidationError(
                ErrorCode.MODE_UNKNOWN,
                f"mode {payload.mode!r} is not {MODE_KNOWLEDGE_ENTITY!r}",
            )
        entity_type = payload.entity_type.strip() if payload.entity_type else None
        if not entity_type:
            raise InterviewValidationError(
                ErrorCode.ENTITY_TYPE_REQUIRED, "the entity interview needs an entity type"
            )
        if entity_type not in ENTITY_TYPES:
            raise InterviewValidationError(
                ErrorCode.ENTITY_TYPE_UNKNOWN,
                f"the entity type {entity_type!r} is not one of {'|'.join(ENTITY_TYPES)}",
            )
        if not await self.novels.exists(payload.novel_id):
            raise InterviewNotFoundError(f"novel {payload.novel_id} is absent or not yours")
        if payload.target_id is not None and not await self.roster.owns_entity(
            payload.novel_id, payload.target_id
        ):
            # The target is a stored reference, so it is checked like the
            # novel: absent, another user's and another novel's answer one 404
            # with one body, the id never quoted back.
            raise InterviewNotFoundError("the target is absent or not yours in this novel")
        session = await self.sessions.create(
            payload.novel_id, payload.mode, entity_type, payload.target_id
        )
        await self.session.commit()
        return session

    async def list_sessions(self, novel_id: UUID) -> list[SessionListRow]:
        """The user's interviews in the novel: open first, then closed, newest first."""
        if not await self.novels.exists(novel_id):
            raise InterviewNotFoundError(f"novel {novel_id} is absent or not yours")
        return await self.sessions.list_for_novel(novel_id)

    async def read_session(self, session_id: UUID) -> AssistantSession:
        """The session with the transcript, up to ``TRANSCRIPT_READ_LIMIT`` turns, as ``turns``."""
        session = await self.sessions.get(session_id)
        if session is None:
            raise InterviewNotFoundError("the session is absent or not yours")
        turns = await self.sessions.last_turns(session_id, TRANSCRIPT_READ_LIMIT)
        # The detail's schema reads the transcript off the row; the model has
        # no relationship, so the read attaches the loaded list.
        session.turns = turns  # pyright: ignore[reportAttributeAccessIssue]
        return session

    async def close_session(self, session_id: UUID) -> AssistantSession:
        """End the interview; closing an already closed one changes nothing."""
        session = await self.sessions.get(session_id)
        if session is None:
            raise InterviewNotFoundError("the session is absent or not yours")
        if session.closed_at is None:
            await self.sessions.close(session)
            await self.session.commit()
        return session

    async def take_turn(self, session_id: UUID, payload: TurnCreate) -> TurnReadback:
        """Run one turn's three steps: the short read, the call, the write."""
        model_act = payload.act in MODEL_ACTS
        state = await self._read_turn_state(session_id, with_prompt=model_act)
        # Closed answers first, before the turn's own validation: the spec's
        # table gives a turn against a closed session one answer, and step 3
        # checks closed before it reads a suggestion too.
        if state.closed:
            raise SessionClosedError(f"session {session_id} was closed")
        text = payload.text
        pending_seq: int | None = None
        if payload.act == "accept-suggestion":
            pending = await self._pending_suggestion(session_id)
            pending_seq = pending.seq if pending is not None else None
            text = _accepted_text(payload.text, pending.suggestion if pending else None)
        await self.session.commit()
        # The read's rows leave the identity map: step 3 must load the session
        # as it stands under the lock, not as step 1 saw it.
        self.session.expunge_all()

        calls: list[AuditedCall] = []
        resolved: ResolvedProvider | None = None
        answer: InterviewAnswer | None = None
        if model_act:
            try:
                prompt = await self._render_prompt(state, payload, text)
            except PromptRenderError as error:
                raise PromptRefusedError(str(error)) from None
            try:
                resolved = await resolve_provider(self.session, self.user_id, CHAT_KEY)
            except Exception as error:
                raise ProviderUnavailableError(str(error)) from None
            # The prompt's override read and resolution end here: nothing
            # reads the database while the provider is answering.
            await self.session.commit()
            answer = await self._ask(prompt, state.novel_id, calls, resolved)
        return await self._write_turn(state, payload, text, answer, calls, resolved, pending_seq)

    async def _read_turn_state(self, session_id: UUID, *, with_prompt: bool) -> _TurnState:
        """Step 1: the session, its proposal and the turns the prompt may need."""
        session = await self.sessions.get(session_id)
        if session is None:
            raise InterviewNotFoundError("the session is absent or not yours")
        # The writer's current turn takes the transcript's last place, so the
        # model reads at most twenty conversation turns including this answer.
        turns = await self.sessions.last_turns(session_id, TRANSCRIPT_LIMIT - 1)
        heading: tuple[str, str | None] = ("", None)
        roster: list[Entity] = []
        roster_cut = False
        if with_prompt and session.closed_at is None:
            found = await self.novels.heading(session.novel_id)
            heading = found if found is not None else ("", None)
            entities = await self.roster.names_for_novel(session.novel_id, ROSTER_LIMIT + 1)
            roster_cut = len(entities) > ROSTER_LIMIT
            roster = entities[:ROSTER_LIMIT]
        return _TurnState(
            session_id=session.id,
            novel_id=session.novel_id,
            entity_type=session.entity_type or "",
            proposal=session.proposal,
            closed=session.closed_at is not None,
            turns=turns,
            heading=heading,
            roster=roster,
            roster_cut=roster_cut,
        )

    async def _render_prompt(self, state: _TurnState, payload: TurnCreate, text: str) -> str:
        """Step 2: render the registered interview prompt for this turn."""
        title, genre = state.heading
        lines = [
            turn_line(ASSISTANT_PREFIX if turn.role == "assistant" else USER_PREFIX, turn.text)
            for turn in state.turns
        ]
        lines.append(turn_line(USER_PREFIX, text))
        variables: dict[str, object] = {
            **novel_variables(title, genre or ""),
            "entity_type": state.entity_type,
            "slots": json.dumps(_proposal_slots(state.proposal), ensure_ascii=False),
            "relations": json.dumps(_relations_for_prompt(state.proposal), ensure_ascii=False),
            "transcript": "\n".join(lines),
            "roster": roster_for_prompt(state.roster, state.roster_cut),
            "request": payload.act or "answer",
        }
        return await render(
            self.session,
            self.user_id,
            INTERVIEW_KEY,
            variables,
            novel_id=state.novel_id,
        )

    async def _ask(
        self,
        prompt: str,
        novel_id: UUID,
        calls: list[AuditedCall],
        resolved: ResolvedProvider,
    ) -> InterviewAnswer:
        """Step 2's call: the structured ask, its audit collected while it runs."""

        async def audit(call: AuditedCall) -> None:
            calls.append(call)

        recorder = _PromptRecorder(resolved.provider)
        try:
            return await ask_structured(
                recorder,
                prompt,
                schema=INTERVIEW_SCHEMA,
                parse=_parse_answer,
                audit=audit,
            )
        except MalformedAnswerError as error:
            reason = str(error) or "the answer is not the contracted JSON"
            # Each completed attempt's own read decides its row: both failed
            # here, and each carries the reason its own answer gave.
            await self._write_calls(calls, resolved, novel_id)
            raise ExtractionFailedError(reason) from None
        except Exception as error:
            # The attempt that raised never reached the audit callback; its row
            # is written here, with the prompt the recorder kept for it. A
            # completed attempt before it keeps its own outcome: a malformed
            # first answer stays extraction-failed beside this provider error.
            failed = AuditedCall(
                prompt=recorder.prompt or prompt,
                answer="",
                latency_ms=recorder.latency_ms,
                usage=None,
            )
            await self._write_calls(
                calls,
                resolved,
                novel_id,
                failed=failed,
                error=_failure_name(error),
                error_code="provider-error",
            )
            raise ProviderCallError(_failure_name(error)) from None

    async def _write_turn(
        self,
        state: _TurnState,
        payload: TurnCreate,
        text: str,
        answer: InterviewAnswer | None,
        calls: list[AuditedCall],
        resolved: ResolvedProvider | None,
        accepted_seq: int | None,
    ) -> TurnReadback:
        """Step 3: lock, allocate, write, merge and audit in one transaction.

        ``accepted_seq`` is the suggestion step 1 settled on: step 3 accepts
        only that same turn, still pending, so a suggestion another turn
        created while the model answered is never accepted under an answer
        prepared for its predecessor.
        """
        locked = await self.sessions.lock(state.session_id)
        if locked is None:
            await self.session.rollback()
            if resolved is not None:
                await self._write_calls(
                    calls,
                    resolved,
                    state.novel_id,
                    status="error",
                    error_code="not-found",
                    error="the session is absent or not yours",
                )
            raise InterviewNotFoundError("the session is absent or not yours")
        if locked.closed_at is not None:
            await self.session.rollback()
            if resolved is not None:
                # The rollback expired every identity-map row: read the novel
                # from the step-1 state, never from ``locked`` after it.
                await self._write_calls(
                    calls,
                    resolved,
                    state.novel_id,
                    status="error",
                    error_code="session-closed",
                    error=f"session {state.session_id} was closed",
                )
            raise SessionClosedError(f"session {state.session_id} was closed")

        pending: AssistantTurn | None = None
        if payload.act == "accept-suggestion":
            pending = await self._pending_suggestion(state.session_id)
            if pending is None or pending.seq != accepted_seq:
                reason = "the pending suggestion changed while the answer was prepared"
                await self.session.rollback()
                if resolved is not None:
                    await self._write_calls(
                        calls,
                        resolved,
                        state.novel_id,
                        status="error",
                        error_code="suggestion-mismatch",
                        error=reason,
                    )
                raise InterviewValidationError(ErrorCode.SUGGESTION_MISMATCH, reason)
            try:
                text = _accepted_text(payload.text, pending.suggestion)
            except InterviewValidationError as error:
                await self.session.rollback()
                if resolved is not None:
                    await self._write_calls(
                        calls,
                        resolved,
                        state.novel_id,
                        status="error",
                        error_code=error.code,
                        error=str(error),
                    )
                raise

        seq = await self.sessions.next_seq(state.session_id)
        await self.sessions.append_turn(state.session_id, seq, "user", text, act=payload.act)

        if payload.act == "reject-suggestion":
            pending = await self._pending_suggestion(state.session_id)
            if pending is not None:
                await self.sessions.set_suggestion_state(pending, "rejected")
            await self.session.commit()
            return TurnReadback(
                reply=None,
                proposal=_read_proposal(locked.proposal),
                suggestion=None,
                seq=seq,
            )

        if payload.act == "drop-suggestions":
            proposal = _drop_suggested(locked.proposal)
            await self.sessions.set_proposal(locked, proposal)
            await self.session.commit()
            return TurnReadback(
                reply=None,
                proposal=_read_proposal(proposal),
                suggestion=None,
                seq=seq,
            )

        if answer is None or resolved is None:
            # Unreachable while MODEL_ACTS and the three acts agree; the
            # check keeps the write path typed without an assert in production.
            raise ProviderCallError("the model act produced no answer")

        if payload.act == "accept-suggestion" and pending is not None:
            await self.sessions.set_suggestion_state(pending, "accepted")

        suggestion = None
        if answer.suggestion is not None:
            suggestion = single_line(answer.suggestion) or None
        assistant_seq = seq + 1
        await self.sessions.append_turn(
            state.session_id,
            assistant_seq,
            "assistant",
            answer.reply,
            suggestion=suggestion,
            suggestion_state="pending" if suggestion is not None else None,
        )
        if payload.act == "no-idea":
            # The model proposes an answer to its last question; the proposal
            # is not changed, so a guessed slot never becomes the writer's.
            proposal = locked.proposal
        else:
            proposal = _merge_proposal(locked.proposal, state.proposal, answer, payload.act)
            await self.sessions.set_proposal(locked, proposal)
        await self._record_calls(calls, resolved, locked.novel_id)
        await self.session.commit()
        return TurnReadback(
            reply=answer.reply,
            proposal=_read_proposal(proposal),
            suggestion=suggestion,
            seq=assistant_seq,
        )

    async def _pending_suggestion(self, session_id: UUID) -> AssistantTurn | None:
        """The newest suggestion still pending, read over the whole transcript.

        Step 1 reads it for an accepted turn, so the prompt carries the settled
        answer; step 3 re-reads it under the session's lock, which is the
        authoritative read the settlement uses. The two settlement acts name
        the suggestion the panel showed, which may be older than the prompt's
        twenty-turn window; the read is the transcript, up to
        ``TRANSCRIPT_READ_LIMIT`` turns, so a suggestion is settled however long
        the interview ran.
        """
        turns = await self.sessions.last_turns(session_id, TRANSCRIPT_READ_LIMIT)
        return _pending(turns)

    async def _write_calls(
        self,
        calls: list[AuditedCall],
        resolved: ResolvedProvider,
        novel_id: UUID,
        *,
        status: str = "ok",
        error: str | None = None,
        error_code: str | None = None,
        failed: AuditedCall | None = None,
    ) -> None:
        """A failed turn's audit rows, alone in their own short transaction.

        ``calls`` are the attempts that returned; a row whose attempt's answer
        did not parse is its own ``extraction-failed`` row with that attempt's
        reason, the rest take ``status``/``error_code``. ``failed`` is the
        attempt that raised, always an error row with the turn's reason.
        """
        if not calls and failed is None:
            return
        await self._record_calls(
            calls, resolved, novel_id, status=status, error=error, error_code=error_code
        )
        if failed is not None:
            await self._record_calls(
                [failed], resolved, novel_id, status="error", error=error, error_code=error_code
            )
        await self.session.commit()

    async def _record_calls(
        self,
        calls: list[AuditedCall],
        resolved: ResolvedProvider,
        novel_id: UUID,
        *,
        status: str = "ok",
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """One audit row per provider attempt in the caller's transaction.

        A completed attempt whose answer did not parse tells its own outcome:
        ``error``/``extraction-failed`` and the parse reason, whatever the
        turn's later fate was. Every other row takes the caller's status.
        """
        for call in calls:
            parsed = call.parse_error is None
            await record_call(
                self.session,
                user_id=self.user_id,
                task_key=CHAT_KEY,
                prompt_key=INTERVIEW_KEY,
                provider_kind=resolved.kind,
                model=resolved.model,
                latency_ms=call.latency_ms,
                status=status if parsed else "error",
                prompt_text=call.prompt,
                response_text=call.answer,
                error=error if parsed else call.parse_error,
                error_code=error_code if parsed else "extraction-failed",
                input_tokens=call.usage.input_tokens if call.usage else None,
                output_tokens=call.usage.output_tokens if call.usage else None,
                novel_id=novel_id,
                profile_id=resolved.profile_id,
                base_url=resolved.base_url,
                kind=resolved.kind,
                info=resolved.info,
            )
