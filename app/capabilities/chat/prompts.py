"""The chat prompts. Chat owns its prompt text, per the spec.

The source prefix is a kernel constant: the fake provider quotes such a line,
so a test can see that retrieval reached the model boundary. A real provider
reads the instruction above it and ignores the marker. The passage lines
arrive pre-joined behind the marker (`sources_block`) — the template never
writes the marker itself, and the contract refuses a template that drops
`{{ sources }}`, so a re-voiced frame cannot lose the sources.

The interview is chat's second prompt: a turn-based conversation that asks
about one new entity and proposes it. Its machine markers are kernel
constants — the template renders each on its marker line, the contract
requires every prefix, and the fake reads exactly those lines. The template
carries one question track per entity type, selected by the TYPE line, so what
a figure is asked differs from what a place or an event is asked without
touching code. The key rides the `chat.ask` task: the interview is a chat, and
a fifth assignable task would change the settings screen for no user-visible
gain.
"""

import json
from collections.abc import Sequence  # noqa: TC003
from typing import Final

from app.capabilities.chat.repository import EntityRosterRepository
from app.kernel.contracts.models import Entity  # noqa: TC001
from app.kernel.llm import (
    ASSISTANT_PREFIX,
    INTERVIEW_MARKERS,
    PURPOSE_INTERVIEW,
    PURPOSE_PREFIX,
    RELATIONS_PREFIX,
    SLOTS_PREFIX,
    SOURCE_PREFIX,
    USER_PREFIX,
    single_line,
)
from app.kernel.prompts import (
    AssembledContext,
    LiveTestContext,
    get_registry,
    no_includes,
    render,
    render_source,
)
from app.kernel.retrieval import Passage, PassageRepository

CHAT_KEY: Final = "chat.ask"
INTERVIEW_KEY: Final = "knowledge.entity-interview"

RETRIEVAL_LIMIT: Final = 5
"""How many passages the assembled prompt may cite.

The request schema's default and the live test's retrieval share it, so the
editor's test rides what a real ask rides. The schema imports it from here
— this module is the one home, and importing it back would be a cycle.
"""

CHAT_TEMPLATE = (
    "Answer the question using only the sources below. Quote the passage that "
    "carries the answer verbatim, and do not add knowledge from outside them.\n\n"
    "Question: {{ question }}\n\n"
    "Sources:\n{{ sources }}\n"
)


_SAMPLE_QUESTION: Final = "Wo war der Leuchtturm?"
_SAMPLE_PASSAGE: Final = "Der Leuchtturm am Horizont war seit Jahren dunkel."


def _source_line(text: str) -> str:
    """One marked source line — the one place the marker and text are joined.

    ``sources_block`` builds the runtime lines with it and ``sample_variables``
    builds the sample's line with it, so the payload the contract binds cannot
    drift from the format an override actually receives.
    """
    return f"{SOURCE_PREFIX}{text}"


def sources_block(passages: Sequence[Passage]) -> str:
    """The source lines, each behind the kernel's marker — today's join."""
    return "\n".join(_source_line(passage.text) for passage in passages)


def sample_variables() -> dict[str, object]:
    """The sample the editor's legend and the save-time validation render.

    The sources arrive as the marker-carrying block an override receives —
    what its author may reorder, never rewrite.
    """
    return {
        "question": _SAMPLE_QUESTION,
        "sources": _source_line(_SAMPLE_PASSAGE),
    }


_SAMPLE_SOURCES: Final[str] = str(sample_variables()["sources"])
"""The sample's own marked sources line: the payload the contract binds whole."""


def chat_contract(rendered: str) -> bool:
    """A re-voice may reorder the frame, never drop the marked sources.

    Content-bound, mirroring the knowledge capability's settled shape (the
    predicate is duplicated, not imported — one capability does not reach
    into another): the marker alone is not enough. The sample's own marked
    sources line must ride the render whole, so a template that drops
    ``{{ sources }}`` — or keeps only a bare ``SOURCE: `` line, or merely
    mentions the marker in prose — fails the save-time gate instead of
    reaching the model and answering ungrounded.
    """
    return SOURCE_PREFIX in rendered and _SAMPLE_SOURCES in rendered


def chat_prompt(*, question: str, passages: Sequence[Passage]) -> str:
    """The bundled chat prompt, rendered offline through the registry's template.

    The same arrangement the chain render runs; no production caller remains —
    the service renders through the registry, and the golden pins this path
    byte for byte.
    """

    return render_source(
        CHAT_TEMPLATE,
        {"question": question, "sources": sources_block(passages)},
        include=no_includes,
    )


INTERVIEW_TEMPLATE = (
    f"{PURPOSE_PREFIX}{PURPOSE_INTERVIEW}\n"
    "\n"
    "You are interviewing the writer to build one new entity for the novel "
    '"{{ novel_title }}"{% if novel_genre %} in the genre {{ novel_genre }}{% endif %}.\n'
    "Ask exactly one question per turn — the most useful one for this entity — and\n"
    "never tell the writer what type of entity it is. When nothing useful is left\n"
    "to ask, say so in your reply and stop.\n"
    "\n"
    "Question tracks by entity type; use the one the TYPE line names:\n"
    '{% if entity_type == "character" %}'
    "- name and role: what is the character called, and what part do they play?\n"
    "- appearance: what does the writer see when this character enters a scene?\n"
    "- want and fear: what do they want, and what are they afraid of?\n"
    "- how they speak: what do their words sound like on the page?\n"
    "- who they trust and who they oppose: who stands with them, who against?\n"
    "- what they hide: what do they keep from the other figures?\n"
    '{% elif entity_type == "location" %}'
    "- name and kind of place: what is it called, and what kind of place is it?\n"
    "- what it looks, sounds and smells like: what meets the senses there?\n"
    "- who goes there: who visits, lives or works in this place?\n"
    "- what happened there: which events left their mark on it?\n"
    '{% elif entity_type == "faction" %}'
    "- name and purpose: what is it called, and what does it want?\n"
    "- who leads it: who holds it together?\n"
    "- who belongs: who counts as a member?\n"
    "- how it acts: what does it do when it moves against the story?\n"
    "- friends and enemies: who stands with it, and who stands against it?\n"
    '{% elif entity_type == "object" %}'
    "- name and kind: what is it called, and what kind of thing is it?\n"
    "- what it does or opens: what changes when someone uses it?\n"
    "- who made or owns it: whose hands shaped it, and whose hands hold it?\n"
    "- where it comes from: where did it begin, and how did it get here?\n"
    '{% elif entity_type == "system" %}'
    "- name and purpose: what is it called, and what is it for?\n"
    "- how it works and its limits: what can it do, and where does it stop?\n"
    "- who runs or relies on it: who keeps it going, and who needs it?\n"
    "- how it fails: what breaks when it is pushed too far?\n"
    '{% elif entity_type == "timeline" %}'
    "- name and span: what is it called, and which years does it cover?\n"
    "- what marks beginning and end: which events open and close it?\n"
    "- what it changes: what is different because it exists?\n"
    "- who keeps it: who records, remembers or guards it?\n"
    '{% elif entity_type == "event" %}'
    "- name and when: what is it called, and when does it happen?\n"
    "- what happened: what actually takes place?\n"
    "- who took part: who stands in the middle of it?\n"
    "- what it caused: what follows from it, near and far?\n"
    "{% else %}"
    "- name: what is it called?\n"
    "- what it is: what is it, in one sentence?\n"
    "- what belongs to it: what is tied to it or hangs off it?\n"
    "{% endif %}\n"
    "Ask about the writer's own story, not about writing craft in general. Propose\n"
    "relations only to names on the roster below or to names the writer has already\n"
    "given; never invent a target. The roster is capped at 200 names — a list that\n"
    "stops at 200 is cut, so say so and ask instead of assuming it is complete. If\n"
    "what the writer describes is already on the roster by name or alias, say so\n"
    "and ask whether they mean that existing entity before going further.\n"
    "\n"
    "The writer's request for this turn; the REQUEST line names the act:\n"
    "- answer: the writer replied. Take what the reply says and ask the next question.\n"
    "- accept-suggestion: the writer takes your last suggestion. Record it as the\n"
    "  writer's own answer and continue.\n"
    "- no-idea: the writer has no idea. Offer one concrete suggestion for the open\n"
    "  slot that fits the story so far.\n"
    "- fill-all: propose every open slot at once from the story so far and this\n"
    "  type's track, plus one relation to a roster name when one fits.\n"
    "\n"
    'Answer with a JSON object and nothing else: {"reply": string, "slots":\n'
    '{"name": string, "aliases": [string], "tags": [string], "content": string},\n'
    '"relations": [{"target": string, "type": string, "note": string}],\n'
    '"suggestion": string}. "slots" is the complete state so far: every value known,\n'
    'not only what changed, and a slot with no value is left out. "suggestion" is\n'
    'present only after no-idea. "relations" carries every proposal so far, and an\n'
    "empty list when there is none.\n"
    "\n"
    "TYPE: {{ entity_type }}\n"
    "SLOTS: {{ slots }}\n"
    "RELATIONS: {{ relations }}\n"
    "TURNS:\n"
    "{# every turn is one line — single_line — so a writer's text can never forge a marker #}"
    "{{ transcript }}\n"
    "ROSTER:\n"
    "{{ roster }}\n"
    "REQUEST: {{ request }}\n"
)

_SAMPLE_ENTITY_TYPE: Final = "character"
_SAMPLE_SLOTS: Final[dict[str, object]] = {}
"""The sample's proposal: empty, so the preview shows an interview at its start."""
_SAMPLE_RELATIONS: Final[list[dict[str, str]]] = []
"""The sample proposes no relation until the interview names a target."""
_SAMPLE_TURNS: Final[tuple[tuple[str, str], ...]] = (
    (ASSISTANT_PREFIX, "Wie heißt die Figur, und welche Rolle spielt sie in der Geschichte?"),
    (USER_PREFIX, "Eine Wächterin am See; einen Namen habe ich noch nicht."),
)


def _turn_line(prefix: str, text: str) -> str:
    """One transcript line: the turn's text behind its prefix on a single line.

    The interview's rendering invariant, through the kernel helper. The live
    renderer (Task 7) builds every turn the same way, so a writer's line breaks
    become spaces and the text can never start a line that looks like a marker.
    """
    return f"{prefix}{single_line(text)}"


_SAMPLE_TRANSCRIPT: Final = "\n".join(_turn_line(prefix, text) for prefix, text in _SAMPLE_TURNS)
_SAMPLE_ROSTER: Final = (
    "Mira (character; Die Wanderin)\n"
    "Haus (location; Das Haus am See)\n"
    "Der Winter (event; Das Jahr ohne Sonne)"
)

_SAMPLE_SLOTS_JSON: Final = json.dumps(_SAMPLE_SLOTS, ensure_ascii=False)
_SAMPLE_RELATIONS_JSON: Final = json.dumps(_SAMPLE_RELATIONS, ensure_ascii=False)
_SAMPLE_PAYLOADS: Final[tuple[str, ...]] = (
    f"{SLOTS_PREFIX}{_SAMPLE_SLOTS_JSON}",
    f"{RELATIONS_PREFIX}{_SAMPLE_RELATIONS_JSON}",
    _SAMPLE_TRANSCRIPT,
    _SAMPLE_ROSTER,
)
"""The sample's marked payloads: the interview's contract binds every one whole."""


def roster_block(entities: Sequence[Entity]) -> str:
    """The roster lines the interview's ROSTER marker heads.

    One ``name (type; aliases)`` line per entity, in the repository's
    name-order; an entity without aliases says ``none`` rather than leaving a
    dangling separator. The template never writes the marker itself, and the
    fake reads the lines behind it.
    """
    return "\n".join(
        f"{entity.name} ({entity.type}; {', '.join(entity.aliases) or 'none'})"
        for entity in entities
    )


def interview_sample_variables() -> dict[str, object]:
    """The sample the editor's legend and the save-time validation render.

    The JSON payloads arrive as the marker-carrying strings an override
    receives — what its author may place, never rewrite — and the sample novel
    and roster are the ones the other bundled samples use.
    """
    return {
        "novel_title": "Der Nebel",
        "novel_genre": "Mystery",
        "entity_type": _SAMPLE_ENTITY_TYPE,
        "slots": _SAMPLE_SLOTS_JSON,
        "relations": _SAMPLE_RELATIONS_JSON,
        "transcript": _SAMPLE_TRANSCRIPT,
        "roster": _SAMPLE_ROSTER,
        "request": "answer",
    }


def interview_contract(rendered: str) -> bool:
    """A re-voice may reorder the frame, never drop the machine markers.

    Content-bound, mirroring chat's settled shape: the six marker prefixes
    alone are not enough — an override could write ``SLOTS: n/a``, keep the
    ``TURNS:`` header while dropping the transcript, or mention the markers in
    prose. The fake reads exactly the marked lines, so the sample's own marked
    payloads must ride the render whole; a template that loses one is refused
    at save time instead of answering the wrong shape at the floor tier.
    """
    return (
        f"{PURPOSE_PREFIX}{PURPOSE_INTERVIEW}" in rendered
        and all(marker in rendered for marker in INTERVIEW_MARKERS)
        and all(payload in rendered for payload in _SAMPLE_PAYLOADS)
    )


async def _assemble_interview(context: LiveTestContext) -> AssembledContext:
    """The live test's interview: the sample beside the real roster.

    An interview at a novel's scope reads that novel's real entity roster, so
    the editor's test shows the names the interview will actually see; without
    a novel the sample roster stands. Every other variable — the heading, the
    type, the empty proposal, the transcript and the act — is the sample the
    legend shows, because there is no stored session to ride. The facts name
    the sample type, the sample's two turns and the roster's size, so the
    context frame says what the call carried.
    """
    variables = interview_sample_variables()
    roster_count = len(_SAMPLE_ROSTER.splitlines())
    if context.novel_id is not None:
        entities = await EntityRosterRepository(context.session, context.user_id).names_for_novel(
            context.novel_id
        )
        variables["roster"] = roster_block(entities)
        roster_count = len(entities)
    prompt = await render(
        context.session,
        context.user_id,
        INTERVIEW_KEY,
        variables,
        novel_id=context.novel_id,
        source=context.source,
    )
    return AssembledContext(
        prompt=prompt,
        facts={
            "type": _SAMPLE_ENTITY_TYPE,
            "turns": str(len(_SAMPLE_TRANSCRIPT.splitlines())),
            "roster": str(roster_count),
        },
    )


async def _assemble_live(context: LiveTestContext) -> AssembledContext:
    """The live test's chat: real retrieval, the sample question named in the facts.

    Chat writes nothing (D14), so no stored question exists to reuse — the
    sample question drives the retrieval query and rides the prompt's
    ``question`` variable where the facts frame shows it verbatim; the
    sources are the user's corpus as a real ask retrieves them. The draft
    (or the effective chain) is the source; the import-free assembly reads
    only the kernel, so the registry's import-time build never cycles.
    """
    [vector] = await context.embeddings.embed([_SAMPLE_QUESTION])
    passages = await PassageRepository(context.session, context.user_id).search(
        vector, RETRIEVAL_LIMIT
    )
    prompt = await render(
        context.session,
        context.user_id,
        CHAT_KEY,
        {"question": _SAMPLE_QUESTION, "sources": sources_block(passages)},
        source=context.source,
    )
    return AssembledContext(
        prompt=prompt,
        facts={"question": _SAMPLE_QUESTION, "passages": str(len(passages))},
    )


get_registry().register(
    CHAT_KEY,
    template=CHAT_TEMPLATE,
    sample_variables=sample_variables,
    contract=chat_contract,
    novel_scopable=False,
    assemble=_assemble_live,
)

get_registry().register(
    INTERVIEW_KEY,
    template=INTERVIEW_TEMPLATE,
    sample_variables=interview_sample_variables,
    contract=interview_contract,
    novel_scopable=True,
    assemble=_assemble_interview,
    task_key=CHAT_KEY,
)
