"""The extraction and consistency prompts. Knowledge owns its prompt text, per the spec.

The chapter rides behind the kernel source marker, the way a retrieval passage
does: the fake provider reads the marker — and derives its answer from the
passage behind it — while a real provider reads the instruction above it. The
purpose marker names which machine-checked answer shape a prompt wants: the
fake branches on the marked line, so the answer shape is declared by the
prompt, not sniffed from its prose.

The bundled arrangements are `EXTRACTION_TEMPLATE` and `CONSISTENCY_TEMPLATE`;
an override of either key — per novel or global — replaces it through the
registry's effective chain. Both templates are over variables only: the
markers arrive inside `purpose_line` and the payload variables and are never
written by a template, and the content-bound contracts are what the save-time
gate runs — the prompts surface, still to dock — so a re-voice that loses the
purpose line or the marked payload is refused, and a bare ``SOURCE: `` line
is a refusal, not a passage.

:class:`ParsedEntity`, :class:`ParsedRelation` and :class:`ParsedFinding`
live here: a contract's ask and its answer shapes are one thing, and both the
handler (which parses) and the repository (which persists) import them from
here — never from each other. The type vocabulary they are checked against
lives beside the model it names, in the kernel contracts (``ENTITY_TYPES``),
and this module imports it from there like every other consumer.
"""

from collections.abc import Callable, Sequence  # noqa: TC003  signatures evaluate
from typing import Final, NamedTuple
from uuid import UUID  # noqa: TC003  signatures evaluate

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002  the assemblies' context

from app.kernel.contracts.models import ENTITY_TYPES, Chapter, Novel
from app.kernel.llm import PURPOSE_PREFIX, SOURCE_PREFIX
from app.kernel.prompts import (
    AssembledContext,
    LiveContextMissingError,
    LiveTestContext,
    get_registry,
    no_includes,
    render,
    render_source,
)

EXTRACTION_KEY: Final = "knowledge.extract-entities"
CONSISTENCY_KEY: Final = "knowledge.check-consistency"

# The purposes the fake branches on (`app.kernel.llm.fake` names the same
# pair). The marked line is the answer shape's declaration: a drifted purpose
# is not refused here but at the first job, where the fake's default prose
# fails the handler's parse loudly.
EXTRACT_PURPOSE: Final = "extract-entities"
CHECK_PURPOSE: Final = "check-consistency"

# The most of a chapter body any prompt carries, in characters. A real model
# overflows on a long chapter; the fake never does, which is why the bound has
# its own tests. Characters, not bytes: a writer's é is one character.
BODY_LIMIT = 20_000

EXTRACTION_TEMPLATE = (
    "{{ purpose_line }}\n"
    "\n"
    "Extract the entities that appear in the chapter below. For each one judge "
    "a type — {{ types }} — and write a one-sentence description of its role. "
    "Then, for each entity, name the relations it has to the other entities "
    "you found: a relation names its target entity and carries a short type "
    '(for example "related_to", "member_of", "located_in"). '
    'Answer with a JSON object containing an "items" array of objects '
    '{"name": string, "type": string, "description": string, '
    '"relations": [{"target": string, "type": string}]} and nothing else: '
    "no prose around it, no commentary. Every entity carries its relations "
    'array, empty when it proposes none. Answer with {"items": []} when the '
    "chapter proposes no entity.\n"
    "\n"
    "Chapter: {{ chapter_title }}\n"
    "Text:\n"
    "{{ sources }}\n"
)

CONSISTENCY_TEMPLATE = (
    "{{ purpose_line }}\n"
    "\n"
    "Read the chapters below as one story and find where the text contradicts "
    "itself: an age that changes between chapters, a date or a timeline that "
    "cannot hold, a name that drifts, a fact stated one way and later another. "
    "For each contradiction write a short summary and a detail that quotes the "
    'readings that disagree. Answer with a JSON object containing an "items" '
    'array of objects {"summary": '
    'string, "detail": string} and nothing else: no prose around it, no '
    'commentary. Answer with {"items": []} when the chapters agree.\n'
    "\n"
    "The story's accepted entities, as grounding:\n"
    "{{ grounding }}\n"
    "\n"
    "{{ chapters }}\n"
)


class ParsedRelation(NamedTuple):
    """One proposed relation of a provider answer, already validated."""

    target: str
    relation_type: str


class ParsedEntity(NamedTuple):
    """One entity of a provider answer, already validated, with the
    relations it proposes to the other named entities."""

    name: str
    type: str
    description: str | None
    relations: list[ParsedRelation]


class ParsedFinding(NamedTuple):
    """One finding of a provider answer, already validated."""

    summary: str
    detail: str | None


def extraction_variables(*, chapter_title: str, body: str) -> dict[str, object]:
    """The extraction template's variables: the chapter behind the source marker.

    The purpose line is the kernel's marker plus this prompt's purpose, and
    ``sources`` is the marked body — a template never writes a marker itself.
    The body arrives cut by the caller (``body[:BODY_LIMIT]`` at the call
    site); the cut is the caller's, never the template's.
    """
    return {
        "purpose_line": f"{PURPOSE_PREFIX}{EXTRACT_PURPOSE}",
        "types": "|".join(ENTITY_TYPES),
        "chapter_title": chapter_title,
        "sources": f"{SOURCE_PREFIX}{body}",
    }


def consistency_variables(
    *, entities: Sequence[tuple[str, str]], chapters: Sequence[tuple[str, str]]
) -> dict[str, object]:
    """The consistency template's variables: the canon and the marked chapters.

    ``entities`` are (name, type) pairs of the novel's accepted entities — the
    story's canon, grounding what a name refers to; an empty canon grounds
    itself with today's placeholder line. ``chapters`` are (title, body) pairs
    in reading order, each body behind the source marker the way a retrieval
    passage is, so the provider boundary sees every chapter and a test steers
    the fake's derivation with the chapter texts alone.
    """
    grounding = "\n".join(f"{name} ({type_})" for name, type_ in entities)
    if not grounding:
        grounding = "None accepted yet."
    chapters_text = "\n\n".join(
        f"Chapter: {title}\nText:\n{SOURCE_PREFIX}{body}" for title, body in chapters
    )
    return {
        "purpose_line": f"{PURPOSE_PREFIX}{CHECK_PURPOSE}",
        "grounding": grounding,
        "chapters": chapters_text,
    }


def sample_variables_extraction() -> dict[str, object]:
    """The sample the editor's legend and the save-time validation render.

    The chapter arrives as the marker-carrying payload an override receives —
    what its author may reorder, never rewrite.
    """
    return extraction_variables(chapter_title="Arrival", body="The fog came from the lake.")


def sample_variables_consistency() -> dict[str, object]:
    """The sample the editor's legend and the save-time validation render."""
    return consistency_variables(
        entities=[("Mira", "character"), ("House", "location")],
        chapters=[
            ("Arrival", "The fog came from the lake."),
            ("Later", "Mira entered the old house."),
        ],
    )


_SAMPLES: Final[dict[str, Callable[[], dict[str, object]]]] = {
    EXTRACT_PURPOSE: sample_variables_extraction,
    CHECK_PURPOSE: sample_variables_consistency,
}


def purpose_contract_factory(purpose: str) -> Callable[[str], bool]:
    """A content-bound contract for a purpose-marked prompt.

    The fake branches on the marked line and derives its answer from the
    marked payload, so a re-voice that loses either is broken at the floor
    tier — the answer shape drifts, or the derivation runs on nothing. The
    contract therefore binds content, not prefixes: the sample's own purpose
    line and the sample's own marked payload (the marked chapter or chapters)
    must ride the render whole. A template that drops ``{{ purpose_line }}``,
    renames the purpose, or keeps the marker as a bare ``SOURCE: `` line
    fails the contract — refused by the save-time gate the prompts surface
    runs it under, not discovered as an empty extraction at job time.
    """
    sample = _SAMPLES[purpose]()
    payloads = [
        value for value in sample.values() if isinstance(value, str) and SOURCE_PREFIX in value
    ]
    purpose_line = f"{PURPOSE_PREFIX}{purpose}"

    def contract(rendered: str) -> bool:
        return purpose_line in rendered and all(payload in rendered for payload in payloads)

    return contract


extraction_contract = purpose_contract_factory(EXTRACT_PURPOSE)
consistency_contract = purpose_contract_factory(CHECK_PURPOSE)


def extraction_prompt(*, chapter_title: str, body: str) -> str:
    """The bundled extraction prompt, rendered offline through the registry's template.

    The same arrangement the chain render runs; no production caller remains —
    the jobs render through the registry, and the golden pins this path byte
    for byte.
    """

    return render_source(
        EXTRACTION_TEMPLATE,
        extraction_variables(chapter_title=chapter_title, body=body),
        include=no_includes,
    )


def consistency_prompt(
    *, entities: Sequence[tuple[str, str]], chapters: Sequence[tuple[str, str]]
) -> str:
    """The bundled consistency prompt, rendered offline through the registry's template.

    The same arrangement the chain render runs; no production caller remains —
    the jobs render through the registry, and the golden pins this path byte
    for byte.
    """

    return render_source(
        CONSISTENCY_TEMPLATE,
        consistency_variables(entities=entities, chapters=chapters),
        include=no_includes,
    )


async def _latest_chapter(
    session: AsyncSession, user_id: UUID, novel_id: UUID | None
) -> Chapter | None:
    """The user's most recently touched chapter — the live test's extraction unit.

    Scoped to one novel when the request names one; across the whole atelier
    otherwise. ``updated_at`` answers "touched", the same writer's-edge rule
    the writing assembly's scene pick runs.
    """
    statement = select(Chapter).where(Chapter.user_id == user_id)
    if novel_id is not None:
        statement = statement.where(Chapter.novel_id == novel_id)
    return await session.scalar(
        statement.order_by(Chapter.updated_at.desc(), Chapter.id.desc()).limit(1)
    )


async def _latest_novel(
    session: AsyncSession, user_id: UUID, novel_id: UUID | None
) -> Novel | None:
    """The scope's novel, or the user's most recently touched one."""
    statement = select(Novel).where(Novel.user_id == user_id)
    if novel_id is not None:
        statement = statement.where(Novel.id == novel_id)
    return await session.scalar(
        statement.order_by(Novel.updated_at.desc(), Novel.id.desc()).limit(1)
    )


async def _assemble_extraction(context: LiveTestContext) -> AssembledContext:
    """The live test's extraction: the latest chapter's prose, the real scope.

    The same variables the extraction job builds — the chapter title, the
    prose its scenes carry, the body cut to the bound at the caller, never
    the template — rendered at the request's scope with the draft (or the
    effective chain) as the source. The import is deferred: this module
    registers at import time and the jobs module imports it.
    """
    from app.capabilities.knowledge.jobs import BODY_LIMIT, prose_by_chapter

    chapter = await _latest_chapter(context.session, context.user_id, context.novel_id)
    if chapter is None:
        raise LiveContextMissingError("no chapter to extract from yet — write a chapter first")
    prose = (await prose_by_chapter(context.session, context.user_id, [chapter.id])).get(
        chapter.id, ""
    )
    prompt = await render(
        context.session,
        context.user_id,
        EXTRACTION_KEY,
        extraction_variables(chapter_title=chapter.title, body=prose[:BODY_LIMIT]),
        novel_id=context.novel_id,
        source=context.source,
    )
    novel = await _latest_novel(context.session, context.user_id, chapter.novel_id)
    facts = {"chapter": chapter.title, "chars": str(min(len(prose), BODY_LIMIT))}
    if novel is not None:
        facts = {"novel": novel.title, **facts}
    return AssembledContext(prompt=prompt, facts=facts)


async def _assemble_consistency(context: LiveTestContext) -> AssembledContext:
    """The live test's consistency: one real pass over the scope's book.

    The same assembly the consistency job runs — the novel's accepted
    entities as the canon, its chapters packed greedily under the body bound
    — reduced to the first group: one pass is one provider call, what the
    live test's rate limit and audit budget for. The facts name the novel,
    the chapters the pass carries and the canon's size, so a reader sees
    the pass's reach.
    """
    from app.capabilities.knowledge.jobs import chapter_groups, prose_by_chapter
    from app.capabilities.knowledge.repository import EntityRepository

    novel = await _latest_novel(context.session, context.user_id, context.novel_id)
    if novel is None:
        raise LiveContextMissingError("no novel to check yet — create a book with chapters first")
    chapters = (
        await context.session.scalars(
            select(Chapter)
            .where(Chapter.novel_id == novel.id, Chapter.user_id == context.user_id)
            .order_by(Chapter.position)
        )
    ).all()
    entities = await EntityRepository(context.session, context.user_id).list_for_novel(novel.id)
    canon = [(entity.name, entity.type) for entity in entities]
    prose = await prose_by_chapter(
        context.session, context.user_id, [chapter.id for chapter in chapters]
    )
    groups, _skipped = chapter_groups(chapters, prose)
    if not groups:
        raise LiveContextMissingError(
            "no chapter fits one pass — every chapter is over the consistency bound"
        )
    group = groups[0]
    prompt = await render(
        context.session,
        context.user_id,
        CONSISTENCY_KEY,
        consistency_variables(
            entities=canon,
            chapters=[(chapter.title, prose.get(chapter.id, "")) for chapter in group],
        ),
        novel_id=context.novel_id,
        source=context.source,
    )
    return AssembledContext(
        prompt=prompt,
        facts={
            "novel": novel.title,
            "chapters": str(len(group)),
            "entities": str(len(canon)),
        },
    )


get_registry().register(
    EXTRACTION_KEY,
    template=EXTRACTION_TEMPLATE,
    sample_variables=sample_variables_extraction,
    contract=extraction_contract,
    novel_scopable=True,
    assemble=_assemble_extraction,
)

get_registry().register(
    CONSISTENCY_KEY,
    template=CONSISTENCY_TEMPLATE,
    sample_variables=sample_variables_consistency,
    contract=consistency_contract,
    novel_scopable=True,
    assemble=_assemble_consistency,
)
