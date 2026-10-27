"""Knowledge's background jobs: handlers the api app discovers by convention.

One job kind, one function (spec §9 D10). A handler receives its own session
and owns its transaction: the provider call, the filed rows and the audit row
all ride one commit at the end — a malformed answer raises before any row
exists, and the lane records the failure with nothing written.
"""

from json import JSONDecodeError, loads
from typing import TYPE_CHECKING, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.knowledge.prompts import (
    BODY_LIMIT,
    ParsedEntity,
    ParsedFinding,
    ParsedRelation,
    consistency_prompt,
    extraction_prompt,
)
from app.capabilities.knowledge.repository import (
    ConsistencyFindingRepository,
    EntityRepository,
    EntitySuggestionRepository,
)
from app.kernel.contracts.models import ENTITY_TYPES, Chapter, Novel
from app.kernel.llm import get_provider, provider_facts
from app.kernel.llm.audit import record_call

from .structured import AuditedCall, MalformedAnswerError, ask_structured

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.kernel.jobs.models import Job
    from app.kernel.jobs.worker import JobHandler, ProgressReport

KIND = "extract-entities"
KIND_CHECK = "check-consistency"


# The width of EntitySuggestion.name (and Entity.name): String(200). A longer
# name is the provider breaking the contract, and parse_entities is where it
# is refused — the database's own verdict would arrive as a DataError after
# the fact, which is not this contract's error and says nothing about the answer.
MAX_NAME_LENGTH = 200

# The width of ConsistencyFinding.summary: String(200), refused at parse for
# the same reason the name is.
MAX_SUMMARY_LENGTH = 200

# A relation's target names an entity, so it answers to the name column's
# width; its type answers to EntityRelation.relation_type's. Both are refused
# at parse — the database's own verdict would arrive after the fact, as a
# DataError that says nothing about the answer.
MAX_TARGET_LENGTH = 200
MAX_RELATION_TYPE_LENGTH = 80


def _refuse(shape: str, reason: str, shown: object) -> MalformedAnswerError:
    """Build a parse error with at most 200 characters of the rejected value's repr."""
    return MalformedAnswerError(f"not a JSON array of {shape}: {reason} ({repr(shown)[:200]})")


def _items_of(shape: str, document: object) -> list[object]:
    """The answer's items array, refusing every other document shape.

    The root is an object because structured outputs rejects an array root;
    a bare array is therefore a contract violation, not a tolerated variant
    — accepting both would let a prompt regression pass as green.
    """
    if not isinstance(document, dict):
        raise _refuse(shape, "the answer is not an object with an items array", document)
    # JSON object keys are strings by contract (RFC 8259); the cast states
    # that contract on the type level — the value is re-checked right below.
    record = cast("dict[str, object]", document)
    raw_items = record.get("items")
    if not isinstance(raw_items, list):
        raise _refuse(shape, "the answer is not an object with an items array", record)
    # isinstance narrows to list[Unknown]; the cast restates the check above
    # as the type the callers' loops already re-verify per item.
    return cast("list[object]", raw_items)


# The shape parse_entities accepts, sent as the response schema: one place
# holds the ask and the check, so they cannot drift. The root is an object,
# not the array the answers used to be: structured outputs (the OpenAI
# contract the adapter speaks) rejects an array root outright, so the ask
# and the answer share the {"items": [...]} shape. Every item carries its
# relations — required, like the name: an answer that cannot say what it
# proposes is not a valid answer.
ENTITIES_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": list(ENTITY_TYPES)},
                    "description": {"type": ["string", "null"]},
                    "relations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "target": {"type": "string"},
                                "type": {"type": "string"},
                            },
                            "required": ["target", "type"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["name", "type", "description", "relations"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def parse_entities(answer: str) -> list[ParsedEntity]:
    """The provider's answer as entities, or a loud refusal.

    Defensive on purpose: a non-JSON answer, a non-array document or an item
    without a name, or with one too long for its column, with an unknown
    type, a non-string description, or a missing or malformed relations
    array raises, so the job fails and nothing is written — the alternative,
    skipping bad items, would silently shrink the review queue and hide a
    prompt regression behind a green job.

    Raise MalformedAnswerError for these refusals. Names must be nonblank and
    at most 200 characters; descriptions may be absent or null; the relations
    are required — every proposal needs a nonblank target of at most 200
    characters and a nonblank type of at most 80. An empty array returns an
    empty list, and valid strings are preserved without trimming.
    """
    try:
        document: object = loads(answer)
    except JSONDecodeError as error:
        raise _refuse("entities", "the answer is not JSON", answer) from error
    items = _items_of("entities", document)
    entities: list[ParsedEntity] = []
    for entry in items:
        if not isinstance(entry, dict):
            raise _refuse("entities", "an item is not an object", entry)
        # JSON object keys are strings by contract (RFC 8259); the cast states
        # that contract on the type level — every value is still checked below.
        item = cast("dict[str, object]", entry)
        name = item.get("name")
        type_ = item.get("type")
        description = item.get("description")
        if not isinstance(name, str) or not name.strip():
            raise _refuse("entities", "an item has no name", item)
        if len(name) > MAX_NAME_LENGTH:
            raise _refuse(
                # The name's true length rides the reason: the repr below
                # clips the shown item, so without the count a 2000-character
                # name would look like a 200-character one.
                "entities",
                f"an item's name is {len(name)} characters, over the {MAX_NAME_LENGTH} limit",
                item,
            )
        if type_ not in ENTITY_TYPES:
            raise _refuse(
                "entities", f"an item's type is not one of {'|'.join(ENTITY_TYPES)}", item
            )
        if description is not None and not isinstance(description, str):
            raise _refuse("entities", "an item's description is not a string", item)
        entities.append(ParsedEntity(name, type_, description, _parse_relations(item)))
    return entities


def _parse_relations(item: dict[str, object]) -> list[ParsedRelation]:
    """The item's proposals, or a loud refusal: required, and every proposal
    must carry a target and a type the columns can hold."""
    relations = item.get("relations")
    if not isinstance(relations, list):
        raise _refuse("entities", "an item has no relations array", item)
    # isinstance narrows to list[Unknown]; the cast restates the check above
    # as the type the loop below re-verifies per proposal.
    proposals = cast("list[object]", relations)
    parsed: list[ParsedRelation] = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise _refuse("entities", "a relation is not an object", proposal)
        proposal_item = cast("dict[str, object]", proposal)
        target = proposal_item.get("target")
        relation_type = proposal_item.get("type")
        if not isinstance(target, str) or not target.strip():
            raise _refuse("entities", "a relation has no target", proposal_item)
        if len(target) > MAX_TARGET_LENGTH:
            raise _refuse(
                "entities",
                f"a relation's target is {len(target)} characters,"
                f" over the {MAX_TARGET_LENGTH} limit",
                proposal_item,
            )
        if not isinstance(relation_type, str) or not relation_type.strip():
            raise _refuse("entities", "a relation has no type", proposal_item)
        if len(relation_type) > MAX_RELATION_TYPE_LENGTH:
            raise _refuse(
                "entities",
                f"a relation's type is {len(relation_type)} characters,"
                f" over the {MAX_RELATION_TYPE_LENGTH} limit",
                proposal_item,
            )
        parsed.append(ParsedRelation(target, relation_type))
    return parsed


# The shape parse_findings accepts, sent as the response schema: one place
# holds the ask and the check, so they cannot drift.
# The object root is the structured-outputs contract (see ENTITIES_SCHEMA).
FINDINGS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "detail": {"type": ["string", "null"]},
                },
                "required": ["summary", "detail"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def parse_findings(answer: str) -> list[ParsedFinding]:
    """The provider's answer as findings, or a loud refusal.

    Defensive the way parse_entities is: a non-JSON answer, a non-array
    document, an item that is not an object, without a summary, with a blank
    or over-long one, or with a non-string detail raises, so the job fails
    and nothing is written — the alternative, skipping bad items, would
    silently shrink the findings queue and hide a prompt regression behind
    a green job.

    Raise MalformedAnswerError for these refusals. Summaries must be nonblank
    and at most 200 characters; details may be absent or null. An empty array
    returns an empty list, and valid strings are preserved without trimming.
    """
    try:
        document: object = loads(answer)
    except JSONDecodeError as error:
        raise _refuse("findings", "the answer is not JSON", answer) from error
    items = _items_of("findings", document)
    findings: list[ParsedFinding] = []
    for entry in items:
        if not isinstance(entry, dict):
            raise _refuse("findings", "an item is not an object", entry)
        item = cast("dict[str, object]", entry)
        summary = item.get("summary")
        detail = item.get("detail")
        if not isinstance(summary, str) or not summary.strip():
            raise _refuse("findings", "an item has no summary", item)
        if len(summary) > MAX_SUMMARY_LENGTH:
            raise _refuse(
                # The summary's true length rides the reason, the way the
                # entity parse's does: the repr below clips the shown item.
                "findings",
                f"an item's summary is {len(summary)} characters,"
                f" over the {MAX_SUMMARY_LENGTH} limit",
                item,
            )
        if detail is not None and not isinstance(detail, str):
            raise _refuse("findings", "an item's detail is not a string", item)
        findings.append(ParsedFinding(summary, detail))
    return findings


async def extract_entities(
    session: AsyncSession, job: Job, report: ProgressReport
) -> dict[str, object]:
    """Read the chapter, prompt the provider, and file pending entity suggestions.

    The chapter is read scoped to the job's owner — a job row is user-owned
    and the work must stay inside that owner's rows. The provider call happens
    here, in the worker, never in a request (D14); everything this handler
    writes commits once at the end, so a raise leaves no half-written queue.

    ``job.payload['chapter_id']`` identifies the chapter as a UUID. Missing or invalid IDs,
    or a chapter missing from the owner's rows, raise ValueError. Invalid
    answers raise MalformedAnswerError; provider and database errors propagate.
    Success commits suggestions and the call audit, reports progress=100
    through the lane's callback, and returns ``suggestions`` as the parsed
    entity count, including duplicates skipped during filing. Provider or
    answer-validation failures create no audit row.
    """
    try:
        chapter_id = UUID(str(job.payload["chapter_id"]))
    except KeyError as error:
        raise ValueError(f"job {job.id} carries no chapter_id") from error
    chapter = await session.scalar(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.user_id == job.user_id)
    )
    if chapter is None:
        # Loud, not skipped: a queued job whose chapter vanished must surface
        # as a failed row the user can see, not disappear from the lane.
        raise ValueError(f"chapter {chapter_id} is gone or not the job owner's")

    body = chapter.body
    truncated = len(body) > BODY_LIMIT
    prompt = extraction_prompt(chapter_title=chapter.title, body=body[:BODY_LIMIT])
    kind, model = provider_facts()

    async def audit(call: AuditedCall) -> None:
        # The audit row rides the handler's terminal commit with the rows it
        # files: the call is part of the work. A raise before the commit — a
        # malformed answer twice over, a dead provider — writes no row; the
        # rollback would take it anyway (D3, D14). The retry audits as its
        # own call because it is one.
        await record_call(
            session,
            user_id=job.user_id,
            task_key="knowledge.extract-entities",
            provider_kind=kind,
            model=model,
            latency_ms=call.latency_ms,
            status="ok",
            prompt_text=call.prompt,
            response_text=call.answer,
            input_tokens=call.usage.input_tokens if call.usage else None,
            output_tokens=call.usage.output_tokens if call.usage else None,
            novel_id=chapter.novel_id,
        )

    entities = await ask_structured(
        get_provider(),
        prompt,
        schema=ENTITIES_SCHEMA,
        parse=parse_entities,
        audit=audit,
    )

    suggestions = EntitySuggestionRepository(session, job.user_id)
    await suggestions.create_many(chapter.novel_id, chapter_id, entities)
    # Progress is the lane's to persist through the report callback — never
    # this session — so the handler's terminal commit stays the only commit
    # the work rides. 100 is the whole job, reported right before returning:
    # the row's status flips only after the handler returns, so 100 never
    # precedes a done row the database lacks.
    await report(100)
    await session.commit()
    return {"suggestions": len(entities), "truncated": truncated}


def _chapter_groups(
    chapters: Sequence[Chapter],
) -> tuple[list[list[Chapter]], list[dict[str, object]]]:
    """Pack chapters into prompt-sized groups in reading order.

    A group carries at most ``BODY_LIMIT`` characters of body, so a pass cannot
    overflow a real model's window. Chapters over the bound on their own come
    back as skipped: a chapter half-read would yield findings that claim a
    completeness the check does not have.
    """
    groups: list[list[Chapter]] = []
    skipped: list[dict[str, object]] = []
    current: list[Chapter] = []
    size = 0
    for chapter in chapters:
        if len(chapter.body) > BODY_LIMIT:
            # Position and stored title, no invented wording: a chapter usually
            # has no title yet (renaming is WP6), and the dock carries the
            # localized fallback. The backend must not speak one locale.
            skipped.append({"position": chapter.position, "title": chapter.title})
            continue
        if current and size + len(chapter.body) > BODY_LIMIT:
            groups.append(current)
            current = []
            size = 0
        current.append(chapter)
        size += len(chapter.body)
    if current:
        groups.append(current)
    return groups, skipped


async def check_consistency(
    session: AsyncSession, job: Job, report: ProgressReport
) -> dict[str, object]:
    """Read the novel in prompt-sized chapter groups and file pending findings.

    Map-reduce over chapters: chapters are packed greedily into groups under
    ``BODY_LIMIT`` (a group is one provider pass), findings are merged across
    groups and deduplicated by summary. A chapter over the bound is never sent
    and is returned as skipped by title — a partially checked chapter would be
    a lie a writer acts on. A novel whose chapters all fit makes exactly one
    pass, which is what the check always did.

    The novel's chapters and entities are read scoped to the job's owner.
    The provider calls happen here, in the worker, never in a request (D14);
    everything this handler writes commits once at the end, so a raise leaves
    no half-written queue. A novel without chapters, or one whose every chapter
    is over the bound, makes no provider call and files no findings.

    ``job.payload['novel_id']`` identifies the novel as a UUID. Missing or invalid IDs,
    or a novel missing from the owner's rows, raise ValueError. Invalid answers
    raise MalformedAnswerError; provider and database errors propagate.
    Progress is reported through the lane's callback after each group; success
    commits findings and every call's audit together, and returns ``findings``
    as the filed count plus ``skipped_chapters``. A failure writes no audit row.
    """
    try:
        novel_id = UUID(str(job.payload["novel_id"]))
    except KeyError as error:
        raise ValueError(f"job {job.id} carries no novel_id") from error
    novel = await session.scalar(
        select(Novel).where(Novel.id == novel_id, Novel.user_id == job.user_id)
    )
    if novel is None:
        # Loud, not skipped: a queued job whose novel vanished must surface
        # as a failed row the user can see, not disappear from the lane.
        raise ValueError(f"novel {novel_id} is gone or not the job owner's")
    chapters = (
        await session.scalars(
            select(Chapter)
            .where(Chapter.novel_id == novel_id, Chapter.user_id == job.user_id)
            .order_by(Chapter.position)
        )
    ).all()
    entities = await EntityRepository(session, job.user_id).list_for_novel(novel_id)

    canon = [(entity.name, entity.type) for entity in entities]
    groups, skipped = _chapter_groups(chapters)
    kind, model = provider_facts()

    async def audit(call: AuditedCall) -> None:
        # One row per pass, riding the terminal commit with the findings: a
        # raise before the commit writes none (D3), and a retry audits as the
        # separate call it is.
        await record_call(
            session,
            user_id=job.user_id,
            task_key="knowledge.check-consistency",
            provider_kind=kind,
            model=model,
            latency_ms=call.latency_ms,
            status="ok",
            prompt_text=call.prompt,
            response_text=call.answer,
            input_tokens=call.usage.input_tokens if call.usage else None,
            output_tokens=call.usage.output_tokens if call.usage else None,
            novel_id=novel_id,
        )

    findings: list[ParsedFinding] = []
    seen: set[str] = set()
    done = 0
    total = sum(len(group) for group in groups)
    if total:
        # A re-run must not inherit the previous run's percentage.
        await report(0)
    for group in groups:
        prompt = consistency_prompt(
            entities=canon,
            chapters=[(chapter.title, chapter.body) for chapter in group],
        )
        found = await ask_structured(
            get_provider(),
            prompt,
            schema=FINDINGS_SCHEMA,
            parse=parse_findings,
            audit=audit,
        )
        for finding in found:
            if finding.summary in seen:
                continue
            seen.add(finding.summary)
            findings.append(finding)
        done += len(group)
        await report(round(done / total * 100))

    repository = ConsistencyFindingRepository(session, job.user_id)
    await repository.create_many(novel_id, findings)
    await report(100)
    await session.commit()
    return {"findings": len(findings), "skipped_chapters": skipped}


# The annotation is the convention the api app reads (``jobs.py`` exporting
# ``handlers``); the explicit type keeps dict invariance honest.
handlers: dict[str, JobHandler] = {KIND: extract_entities, KIND_CHECK: check_consistency}
