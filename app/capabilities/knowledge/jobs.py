"""Knowledge's background jobs: handlers the api app discovers by convention.

One job kind, one function (spec §9 D10). The handler receives its own session
and owns its transaction: the provider call, the suggestion rows and the
progress report all ride one commit at the end — a malformed answer raises
before any row exists, and the lane records the failure with nothing written.
"""

from json import JSONDecodeError, loads
from typing import TYPE_CHECKING, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.knowledge.prompts import ENTITY_KINDS, ParsedEntity, extraction_prompt
from app.capabilities.knowledge.repository import EntitySuggestionRepository
from app.kernel.contracts.models import Chapter
from app.kernel.jobs.models import Job
from app.kernel.llm import get_provider

if TYPE_CHECKING:
    from app.kernel.jobs.worker import JobHandler

KIND = "extract-entities"


class MalformedAnswerError(ValueError):
    """The provider's answer is not the contracted JSON array of entities."""


# The width of EntitySuggestion.name (and Entity.name): String(200). A longer
# name is the provider breaking the contract, and parse_entities is where it
# is refused — the database's own verdict would arrive as a DataError after
# the fact, which is not this contract's error and says nothing about the answer.
MAX_NAME_LENGTH = 200


def _refuse(reason: str, shown: object) -> MalformedAnswerError:
    return MalformedAnswerError(f"not a JSON array of entities: {reason} ({repr(shown)[:200]})")


def parse_entities(answer: str) -> list[ParsedEntity]:
    """The provider's answer as entities, or a loud refusal.

    Defensive on purpose: a non-JSON answer, a non-array document or an item
    without a name, or with one too long for its column, with an unknown
    kind or a non-string description raises, so the job fails and nothing
    is written — the alternative, skipping bad items, would silently shrink
    the review queue and hide a prompt regression behind a green job.
    """
    try:
        document: object = loads(answer)
    except JSONDecodeError as error:
        raise _refuse("the answer is not JSON", answer) from error
    if not isinstance(document, list):
        raise _refuse("the answer is not an array", document)
    # isinstance narrows to list[Unknown]; the cast restates the check above
    # as the type the loop below already re-verifies per item.
    items = cast("list[object]", document)
    entities: list[ParsedEntity] = []
    for entry in items:
        if not isinstance(entry, dict):
            raise _refuse("an item is not an object", entry)
        # JSON object keys are strings by contract (RFC 8259); the cast states
        # that contract on the type level — every value is still checked below.
        item = cast("dict[str, object]", entry)
        name = item.get("name")
        kind = item.get("kind")
        description = item.get("description")
        if not isinstance(name, str) or not name.strip():
            raise _refuse("an item has no name", item)
        if len(name) > MAX_NAME_LENGTH:
            raise _refuse(f"an item's name is longer than {MAX_NAME_LENGTH} characters", item)
        if kind not in ENTITY_KINDS:
            raise _refuse(f"an item's kind is not one of {'|'.join(ENTITY_KINDS)}", item)
        if description is not None and not isinstance(description, str):
            raise _refuse("an item's description is not a string", item)
        entities.append(ParsedEntity(name, kind, description))
    return entities


async def extract_entities(session: AsyncSession, job: Job) -> dict[str, object]:
    """Read the chapter, prompt the provider, file one suggestion per entity.

    The chapter is read scoped to the job's owner — a job row is user-owned
    and the work must stay inside that owner's rows. The provider call happens
    here, in the worker, never in a request (D14); everything this handler
    writes commits once at the end, so a raise leaves no half-written queue.
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
    pieces: list[str] = []
    async for delta in get_provider().stream(prompt):
        pieces.append(delta)
    entities = parse_entities("".join(pieces))

    suggestions = EntitySuggestionRepository(session, job.user_id)
    await suggestions.create_many(chapter.novel_id, chapter_id, entities)
    # Progress is the handler's to report (the worker owns status, not this
    # column), and it rides the same commit as the rows: a reader never sees
    # work claimed that the database does not have. 100 is the whole job —
    # one provider call, nothing incremental worth reporting.
    await session.execute(update(Job).where(Job.id == job.id).values(progress=100))
    await session.commit()
    return {"suggestions": len(entities)}


# The annotation is the convention the api app reads (``jobs.py`` exporting
# ``handlers``); the explicit type keeps dict invariance honest.
handlers: dict[str, JobHandler] = {KIND: extract_entities}
