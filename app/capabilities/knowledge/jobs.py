"""Knowledge's background jobs: handlers the api app discovers by convention.

One job kind, one function (spec §9 D10). A handler receives its own session
and owns its transaction: the provider call, the filed rows, the audit row and
the progress report all ride one commit at the end — a malformed answer raises
before any row exists, and the lane records the failure with nothing written.
"""

from json import JSONDecodeError, loads
from time import monotonic
from typing import TYPE_CHECKING, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.knowledge.prompts import (
    ENTITY_KINDS,
    ParsedEntity,
    ParsedFinding,
    consistency_prompt,
    extraction_prompt,
)
from app.capabilities.knowledge.repository import (
    ConsistencyFindingRepository,
    EntityRepository,
    EntitySuggestionRepository,
)
from app.kernel.contracts.models import Chapter, Novel
from app.kernel.jobs.models import Job
from app.kernel.llm import get_provider, provider_facts
from app.kernel.llm.audit import record_call
from app.kernel.llm.contract import CompletionRequest, Delta, Usage

if TYPE_CHECKING:
    from app.kernel.jobs.worker import JobHandler

KIND = "extract-entities"
KIND_CHECK = "check-consistency"


class MalformedAnswerError(ValueError):
    """The provider's answer is not the contracted JSON array of entities or findings."""


# The width of EntitySuggestion.name (and Entity.name): String(200). A longer
# name is the provider breaking the contract, and parse_entities is where it
# is refused — the database's own verdict would arrive as a DataError after
# the fact, which is not this contract's error and says nothing about the answer.
MAX_NAME_LENGTH = 200

# The width of ConsistencyFinding.summary: String(200), refused at parse for
# the same reason the name is.
MAX_SUMMARY_LENGTH = 200


def _refuse(shape: str, reason: str, shown: object) -> MalformedAnswerError:
    """Build a parse error with at most 200 characters of the rejected value's repr."""
    return MalformedAnswerError(f"not a JSON array of {shape}: {reason} ({repr(shown)[:200]})")


def parse_entities(answer: str) -> list[ParsedEntity]:
    """The provider's answer as entities, or a loud refusal.

    Defensive on purpose: a non-JSON answer, a non-array document or an item
    without a name, or with one too long for its column, with an unknown
    kind or a non-string description raises, so the job fails and nothing
    is written — the alternative, skipping bad items, would silently shrink
    the review queue and hide a prompt regression behind a green job.

    Raise MalformedAnswerError for these refusals. Names must be nonblank and
    at most 200 characters; descriptions may be absent or null. An empty array
    returns an empty list, and valid strings are preserved without trimming.
    """
    try:
        document: object = loads(answer)
    except JSONDecodeError as error:
        raise _refuse("entities", "the answer is not JSON", answer) from error
    if not isinstance(document, list):
        raise _refuse("entities", "the answer is not an array", document)
    # isinstance narrows to list[Unknown]; the cast restates the check above
    # as the type the loop below already re-verifies per item.
    items = cast("list[object]", document)
    entities: list[ParsedEntity] = []
    for entry in items:
        if not isinstance(entry, dict):
            raise _refuse("entities", "an item is not an object", entry)
        # JSON object keys are strings by contract (RFC 8259); the cast states
        # that contract on the type level — every value is still checked below.
        item = cast("dict[str, object]", entry)
        name = item.get("name")
        kind = item.get("kind")
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
        if kind not in ENTITY_KINDS:
            raise _refuse(
                "entities", f"an item's kind is not one of {'|'.join(ENTITY_KINDS)}", item
            )
        if description is not None and not isinstance(description, str):
            raise _refuse("entities", "an item's description is not a string", item)
        entities.append(ParsedEntity(name, kind, description))
    return entities


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
    if not isinstance(document, list):
        raise _refuse("findings", "the answer is not an array", document)
    items = cast("list[object]", document)
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


async def extract_entities(session: AsyncSession, job: Job) -> dict[str, object]:
    """Read the chapter, prompt the provider, and file pending entity suggestions.

    The chapter is read scoped to the job's owner — a job row is user-owned
    and the work must stay inside that owner's rows. The provider call happens
    here, in the worker, never in a request (D14); everything this handler
    writes commits once at the end, so a raise leaves no half-written queue.

    ``job.payload['chapter_id']`` identifies the chapter as a UUID. Missing or invalid IDs,
    or a chapter missing from the owner's rows, raise ValueError. Invalid
    answers raise MalformedAnswerError; provider and database errors propagate.
    Success commits suggestions and progress=100 and returns ``suggestions``
    as the parsed entity count, including duplicates skipped during filing.
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

    prompt = extraction_prompt(chapter_title=chapter.title, body=chapter.body)
    kind, model = provider_facts()
    pieces: list[str] = []
    usage: Usage | None = None
    started = monotonic()
    async for event in get_provider().stream(CompletionRequest.user(prompt)):
        if isinstance(event, Delta):
            pieces.append(event.text)
        elif isinstance(event, Usage):
            usage = event
    answer = "".join(pieces)
    latency_ms = round((monotonic() - started) * 1000)
    entities = parse_entities(answer)

    # The audit row rides the handler's terminal commit with the rows it
    # files: the call is part of the work. A raise before here — a malformed
    # answer, a dead provider — writes no row; the rollback would take it
    # anyway (D3, D14).
    await record_call(
        session,
        user_id=job.user_id,
        task_key="knowledge.extract-entities",
        provider_kind=kind,
        model=model,
        latency_ms=latency_ms,
        status="ok",
        prompt_text=prompt,
        response_text=answer,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        novel_id=chapter.novel_id,
    )

    suggestions = EntitySuggestionRepository(session, job.user_id)
    await suggestions.create_many(chapter.novel_id, chapter_id, entities)
    # Progress is the handler's to report (the worker owns status, not this
    # column), and it rides the same commit as the rows: a reader never sees
    # work claimed that the database does not have. 100 is the whole job —
    # one provider call, nothing incremental worth reporting.
    await session.execute(update(Job).where(Job.id == job.id).values(progress=100))
    await session.commit()
    return {"suggestions": len(entities)}


async def check_consistency(session: AsyncSession, job: Job) -> dict[str, object]:
    """Read every chapter and the accepted canon, then file pending findings.

    The novel's chapters and entities are read scoped to the job's owner —
    a job row is user-owned and the work must stay inside that owner's rows.
    The provider call happens here, in the worker, never in a request (D14);
    everything this handler writes commits once at the end, so a raise leaves
    no half-written queue. A novel without chapters is still sent to the provider;
    an empty answer array is valid.

    ``job.payload['novel_id']`` identifies the novel as a UUID. Missing or invalid IDs,
    or a novel missing from the owner's rows, raise ValueError. Invalid answers
    raise MalformedAnswerError; provider and database errors propagate.
    Success commits findings and progress=100 and returns ``findings`` as the
    parsed finding count, including duplicates skipped during filing.
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

    prompt = consistency_prompt(
        entities=[(entity.name, entity.kind) for entity in entities],
        chapters=[(chapter.title, chapter.body) for chapter in chapters],
    )
    kind, model = provider_facts()
    pieces: list[str] = []
    usage: Usage | None = None
    started = monotonic()
    async for event in get_provider().stream(CompletionRequest.user(prompt)):
        if isinstance(event, Delta):
            pieces.append(event.text)
        elif isinstance(event, Usage):
            usage = event
    answer = "".join(pieces)
    latency_ms = round((monotonic() - started) * 1000)
    findings = parse_findings(answer)

    # The extraction handler's audit contract, unchanged in shape: the row
    # rides the terminal commit, and a failure before here writes none.
    await record_call(
        session,
        user_id=job.user_id,
        task_key="knowledge.check-consistency",
        provider_kind=kind,
        model=model,
        latency_ms=latency_ms,
        status="ok",
        prompt_text=prompt,
        response_text=answer,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        novel_id=novel_id,
    )

    repository = ConsistencyFindingRepository(session, job.user_id)
    await repository.create_many(novel_id, findings)
    # The extraction handler's terminal-commit contract, unchanged: progress
    # rides the same commit as the rows, and 100 is the whole job.
    await session.execute(update(Job).where(Job.id == job.id).values(progress=100))
    await session.commit()
    return {"findings": len(findings)}


# The annotation is the convention the api app reads (``jobs.py`` exporting
# ``handlers``); the explicit type keeps dict invariance honest.
handlers: dict[str, JobHandler] = {KIND: extract_entities, KIND_CHECK: check_consistency}
