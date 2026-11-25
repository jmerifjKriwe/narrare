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
from collections.abc import Mapping  # noqa: TC003  signatures evaluate
from dataclasses import dataclass
from typing import Final, cast
from uuid import UUID  # noqa: TC003  signatures and the dataclass evaluate

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002  the service's field

from app.capabilities.chat.models import AssistantSession, AssistantTurn  # noqa: TC001
from app.capabilities.chat.prompts import CHAT_KEY, INTERVIEW_KEY, roster_block
from app.capabilities.chat.repository import (
    AssistantSessionRepository,
    EntityRosterRepository,
    NovelRepository,
)
from app.capabilities.chat.schemas import (
    Proposal,
    SessionCreate,
    TurnCreate,
    TurnReadback,
)
from app.kernel.contracts.models import ENTITY_TYPES, Entity
from app.kernel.llm import (
    ASSISTANT_PREFIX,
    USER_PREFIX,
    AuditedCall,
    MalformedAnswerError,
    ask_structured,
    single_line,
)
from app.kernel.llm.audit import record_call
from app.kernel.llm.resolution import ResolvedProvider, resolve_provider
from app.kernel.prompts import render

MODE_KNOWLEDGE_ENTITY: Final = "knowledge.entity"
"""The one mode cut 1 carries; the vocabulary is checked at the request boundary."""

MODEL_ACTS: Final[frozenset[str | None]] = frozenset(
    {None, "accept-suggestion", "no-idea", "fill-all"}
)
"""The acts that call the model: a plain turn and the three model answers."""

TRANSCRIPT_LIMIT: Final = 20
"""How many conversation turns the model sees, the writer's current one included."""

ROSTER_LIMIT: Final = 200
"""How many roster entities the model sees before the list is declared cut."""

ROSTER_CUT_LINE: Final = "(more entities exist; they are not listed)"
"""The roster's last line when the bound dropped entities: the template cannot know."""

TURN_HISTORY_LIMIT: Final = 10_000
"""The detail's transcript read: far past any real session, so nothing is hidden."""

NAME_LIMIT: Final = 200
"""The longest name, alias, tag or relation target the dialog stores."""

RELATION_TYPE_LIMIT: Final = 80
"""The longest relation type, as the creation endpoint will also bound it."""

CONTENT_LIMIT: Final = 10_000
"""The longest proposal body."""

RELATIONS_LIMIT: Final = 12
"""How many proposed relations are kept; the rest of the answer is dropped."""

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
    code: str = "refused"


class InterviewNotFoundError(InterviewRefusalError):
    """The session or novel is absent, or another user's: one indistinguishable answer."""

    status = 404
    code = "not-found"


class SessionClosedError(InterviewRefusalError):
    """The interview was ended; its transcript is read-only."""

    status = 409
    code = "session-closed"


class InterviewValidationError(InterviewRefusalError):
    """A body outside the mode's contract, with the reason's own code."""

    status = 422

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


class ExtractionFailedError(InterviewRefusalError):
    """Twice-unreadable model answer; nothing was written."""

    status = 502
    code = "extraction-failed"


class ProviderUnavailableError(InterviewRefusalError):
    """No serving tier answered for ``chat.ask``; the cascade's reason rides along."""

    status = 502
    code = "provider-unavailable"


class ProviderCallError(InterviewRefusalError):
    """The provider call died; the class is named so the reader knows what failed."""

    status = 502
    code = "provider-error"


@dataclass(frozen=True)
class InterviewAnswer:
    """What the model answered, still unnormalised: the parse's typed result."""

    reply: str
    slots: dict[str, object]
    relations: list[dict[str, str]]
    suggestion: str | None


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
    if (name := slot_record.get("name")) is not None:
        if not isinstance(name, str):
            raise ValueError("the answer's name is not a string")
        slots["name"] = name
    if (content := slot_record.get("content")) is not None:
        if not isinstance(content, str):
            raise ValueError("the answer's content is not a string")
        slots["content"] = content
    for key in LABEL_KEYS:
        labels = slot_record.get(key)
        if labels is None:
            continue
        if not isinstance(labels, list):
            raise ValueError(f"the answer's {key} are not a JSON array")
        cleaned: list[str] = []
        for label in cast("list[object]", labels):
            if not isinstance(label, str):
                raise ValueError(f"the answer's {key} are not strings")
            cleaned.append(label)
        slots[key] = cleaned

    raw_relations = record.get("relations", [])
    if not isinstance(raw_relations, list):
        raise ValueError("the answer's relations are not a JSON array")
    relations: list[dict[str, str]] = []
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
    """The answer's slots after the server's normalisation: blank parts dropped."""
    cleaned: dict[str, object] = {}
    name = slots.get("name")
    if isinstance(name, str):
        label = _one_line(name, NAME_LIMIT)
        if label:
            cleaned["name"] = label
    for key in LABEL_KEYS:
        values = slots.get(key)
        if isinstance(values, list):
            labels = _labels(cast("list[str]", values))
            if labels:
                cleaned[key] = labels
    content = slots.get("content")
    if isinstance(content, str):
        body = _one_line(content, CONTENT_LIMIT)
        if body:
            cleaned["content"] = body
    return cleaned


def _normalise_relations(relations: list[dict[str, str]]) -> list[dict[str, str]]:
    """The answer's relations: non-blank, bounded, at most twelve."""
    kept: list[dict[str, str]] = []
    for relation in relations:
        target = _one_line(relation["target"], NAME_LIMIT)
        type_ = _one_line(relation["type"], RELATION_TYPE_LIMIT)
        if not target or not type_:
            continue
        kept.append({"target": target, "type": type_, "note": single_line(relation["note"])})
        if len(kept) == RELATIONS_LIMIT:
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


def _suggested_map(proposal: dict[str, object] | None) -> dict[str, bool]:
    """Which label slots the proposal marks suggested; absent means the writer's."""
    marks = {"aliases": False, "tags": False, "content": False}
    if not proposal:
        return marks
    raw = proposal.get("suggested")
    if not isinstance(raw, dict):
        return marks
    record = cast("dict[str, object]", raw)
    return {key: bool(record.get(key)) for key in marks}


def _relation_key(relation: Mapping[str, object]) -> tuple[str, str, str]:
    """A relation's identity for the merge: its target, type and note."""
    return (
        _text(relation.get("target")).strip().casefold(),
        _text(relation.get("type")),
        _text(relation.get("note")),
    )


def _target_key(relation: Mapping[str, object]) -> str:
    """The case-folded target a relation replaces by."""
    return _text(relation.get("target")).strip().casefold()


def _merge_relations(
    now: list[dict[str, object]],
    given: list[dict[str, object]],
    model: list[dict[str, str]],
    act: str | None,
) -> list[dict[str, object]]:
    """Merge the answer's relations into the locked proposal, per relation.

    A relation the answer carried unchanged is left to the locked proposal; a
    new or changed one is written and takes its provenance from the act. The
    model never removes a relation, so a concurrent turn's row survives.
    """
    merged = [dict(relation) for relation in now]
    positions = {_target_key(relation): index for index, relation in enumerate(merged)}
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
        target = _target_key(relation)
        position = positions.get(target)
        if position is None:
            positions[target] = len(merged)
            merged.append(stored)
        else:
            merged[position] = stored
    return merged


def _merge_proposal(
    now: dict[str, object] | None,
    given: dict[str, object] | None,
    answer: InterviewAnswer,
    act: str | None,
) -> dict[str, object]:
    """The locked proposal with the answer's changes, and only its changes."""
    given_slots = _proposal_slots(given)
    slots = dict(_proposal_slots(now))
    suggested = _suggested_map(now)
    name_suggested = bool(now.get("name_suggested")) if now else False
    for key, value in _normalise_slots(answer.slots).items():
        if value == given_slots.get(key):
            continue
        slots[key] = value
        if key == "name":
            name_suggested = act == "fill-all"
        else:
            suggested[key] = act == "fill-all"
    relations = _merge_relations(
        _proposal_relations(now),
        _proposal_relations(given),
        _normalise_relations(answer.relations),
        act,
    )
    return {
        "name": slots.get("name"),
        "name_suggested": name_suggested and bool(slots.get("name")),
        "aliases": slots.get("aliases", []),
        "tags": slots.get("tags", []),
        "content": slots.get("content", ""),
        "suggested": suggested,
        "relations": relations,
    }


def _drop_suggested(
    proposal: dict[str, object] | None,
) -> dict[str, object] | None:
    """The proposal without any suggested part; what the writer said stays."""
    if proposal is None:
        return None
    slots = _proposal_slots(proposal)
    suggested = _suggested_map(proposal)
    if bool(proposal.get("name_suggested")):
        slots.pop("name", None)
    for key in (*LABEL_KEYS, "content"):
        if suggested[key]:
            slots.pop(key, None)
    relations = [
        dict(relation)
        for relation in _proposal_relations(proposal)
        if not bool(relation.get("suggested"))
    ]
    for relation in relations:
        relation["suggested"] = False
    return {
        "name": slots.get("name"),
        "name_suggested": False,
        "aliases": slots.get("aliases", []),
        "tags": slots.get("tags", []),
        "content": slots.get("content", ""),
        "suggested": {"aliases": False, "tags": False, "content": False},
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


def _failure_name(error: Exception) -> str:
    """The provider error's class, with its message when it carries one."""
    message = str(error)
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


def _roster_for_prompt(entities: list[Entity], cut: bool) -> str:
    """The roster lines, with the cut declared when the bound dropped entities."""
    block = roster_block(entities)
    if not cut:
        return block
    return f"{block}\n{ROSTER_CUT_LINE}" if block else ROSTER_CUT_LINE


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
                "mode-unknown",
                f"mode {payload.mode!r} is not {MODE_KNOWLEDGE_ENTITY!r}",
            )
        entity_type = payload.entity_type.strip() if payload.entity_type else None
        if not entity_type:
            raise InterviewValidationError(
                "entity-type-required", "the entity interview needs an entity type"
            )
        if entity_type not in ENTITY_TYPES:
            raise InterviewValidationError(
                "entity-type-unknown",
                f"the entity type {entity_type!r} is not one of {'|'.join(ENTITY_TYPES)}",
            )
        if not await self.novels.exists(payload.novel_id):
            raise InterviewNotFoundError(f"novel {payload.novel_id} is absent or not yours")
        session = await self.sessions.create(
            payload.novel_id, payload.mode, entity_type, payload.target_id
        )
        await self.session.commit()
        return session

    async def list_sessions(self, novel_id: UUID) -> list[AssistantSession]:
        """The user's interviews in the novel, newest first."""
        if not await self.novels.exists(novel_id):
            raise InterviewNotFoundError(f"novel {novel_id} is absent or not yours")
        return await self.sessions.list_for_novel(novel_id)

    async def read_session(self, session_id: UUID) -> AssistantSession:
        """The session with its whole transcript attached as ``turns``."""
        session = await self.sessions.get(session_id)
        if session is None:
            raise InterviewNotFoundError(f"session {session_id} is absent or not yours")
        turns = await self.sessions.last_turns(session_id, TURN_HISTORY_LIMIT)
        # The detail's schema reads the transcript off the row; the model has
        # no relationship, so the read attaches the loaded list.
        session.turns = turns  # pyright: ignore[reportAttributeAccessIssue]
        return session

    async def close_session(self, session_id: UUID) -> AssistantSession:
        """End the interview; closing an already closed one changes nothing."""
        session = await self.sessions.get(session_id)
        if session is None:
            raise InterviewNotFoundError(f"session {session_id} is absent or not yours")
        if session.closed_at is None:
            await self.sessions.close(session)
            await self.session.commit()
        return session

    async def take_turn(self, session_id: UUID, payload: TurnCreate) -> TurnReadback:
        """Run one turn's three steps: the short read, the call, the write."""
        model_act = payload.act in MODEL_ACTS
        state = await self._read_turn_state(session_id, with_prompt=model_act)
        await self.session.commit()
        # The read's rows leave the identity map: step 3 must load the session
        # as it stands under the lock, not as step 1 saw it.
        self.session.expunge_all()
        if state.closed:
            raise SessionClosedError(f"session {session_id} was closed")

        calls: list[AuditedCall] = []
        resolved: ResolvedProvider | None = None
        answer: InterviewAnswer | None = None
        if model_act:
            prompt = await self._render_prompt(state, payload)
            try:
                resolved = await resolve_provider(self.session, self.user_id, CHAT_KEY)
            except Exception as error:
                raise ProviderUnavailableError(str(error)) from None
            # The prompt's override read and resolution end here: nothing
            # reads the database while the provider is answering.
            await self.session.commit()
            answer = await self._ask(prompt, state.novel_id, calls, resolved)
        return await self._write_turn(state, payload, answer, calls, resolved)

    async def _read_turn_state(self, session_id: UUID, *, with_prompt: bool) -> _TurnState:
        """Step 1: the session, its proposal and the turns the prompt may need."""
        session = await self.sessions.get(session_id)
        if session is None:
            raise InterviewNotFoundError(f"session {session_id} is absent or not yours")
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

    async def _render_prompt(self, state: _TurnState, payload: TurnCreate) -> str:
        """Step 2: render the registered interview prompt for this turn."""
        title, genre = state.heading
        lines = [
            f"{ASSISTANT_PREFIX if turn.role == 'assistant' else USER_PREFIX}"
            f"{single_line(turn.text)}"
            for turn in state.turns
        ]
        lines.append(f"{USER_PREFIX}{single_line(payload.text)}")
        variables: dict[str, object] = {
            "novel_title": single_line(title),
            "novel_genre": single_line(genre or ""),
            "entity_type": state.entity_type,
            "slots": json.dumps(_proposal_slots(state.proposal), ensure_ascii=False),
            "relations": json.dumps(_relations_for_prompt(state.proposal), ensure_ascii=False),
            "transcript": "\n".join(lines),
            "roster": _roster_for_prompt(state.roster, state.roster_cut),
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

        try:
            return await ask_structured(
                resolved.provider,
                prompt,
                schema=INTERVIEW_SCHEMA,
                parse=_parse_answer,
                audit=audit,
            )
        except MalformedAnswerError as error:
            await self._write_calls(calls, resolved, novel_id)
            raise ExtractionFailedError(
                str(error) or "the answer is not the contracted JSON"
            ) from None
        except Exception as error:
            await self._write_calls(calls, resolved, novel_id)
            raise ProviderCallError(_failure_name(error)) from None

    async def _write_turn(
        self,
        state: _TurnState,
        payload: TurnCreate,
        answer: InterviewAnswer | None,
        calls: list[AuditedCall],
        resolved: ResolvedProvider | None,
    ) -> TurnReadback:
        """Step 3: lock, allocate, write, merge and audit in one transaction."""
        locked = await self.sessions.lock(state.session_id)
        if locked is None:
            await self.session.rollback()
            if resolved is not None:
                await self._write_calls(calls, resolved, state.novel_id)
            raise InterviewNotFoundError(f"session {state.session_id} is absent or not yours")
        if locked.closed_at is not None:
            await self.session.rollback()
            if resolved is not None:
                await self._write_calls(calls, resolved, locked.novel_id)
            raise SessionClosedError(f"session {state.session_id} was closed")

        seq = await self.sessions.next_seq(state.session_id)
        await self.sessions.append_turn(
            state.session_id, seq, "user", payload.text, act=payload.act
        )

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

        if payload.act == "accept-suggestion":
            pending = await self._pending_suggestion(state.session_id)
            if pending is not None:
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
        """The newest suggestion still pending, read under the session's lock.

        The two settlement acts name the suggestion the panel showed, which may
        be older than the prompt's twenty-turn window; the read is the whole
        transcript, so a suggestion is settled however long the interview ran.
        """
        turns = await self.sessions.last_turns(session_id, TURN_HISTORY_LIMIT)
        return _pending(turns)

    async def _write_calls(
        self,
        calls: list[AuditedCall],
        resolved: ResolvedProvider,
        novel_id: UUID,
    ) -> None:
        """A failed turn's audit rows, alone in their own short transaction."""
        if not calls:
            return
        await self._record_calls(calls, resolved, novel_id)
        await self.session.commit()

    async def _record_calls(
        self,
        calls: list[AuditedCall],
        resolved: ResolvedProvider,
        novel_id: UUID,
    ) -> None:
        """One audit row per provider attempt in the caller's transaction."""
        for call in calls:
            await record_call(
                self.session,
                user_id=self.user_id,
                task_key=CHAT_KEY,
                prompt_key=INTERVIEW_KEY,
                provider_kind=resolved.kind,
                model=resolved.model,
                latency_ms=call.latency_ms,
                status="ok",
                prompt_text=call.prompt,
                response_text=call.answer,
                input_tokens=call.usage.input_tokens if call.usage else None,
                output_tokens=call.usage.output_tokens if call.usage else None,
                novel_id=novel_id,
                profile_id=resolved.profile_id,
                base_url=resolved.base_url,
                kind=resolved.kind,
                info=resolved.info,
            )
