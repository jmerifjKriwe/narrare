"""The smoke suite over the registry: every bundled prompt renders its golden.

Each bundled key carries a sample-variable factory, and this file pins the
render of every bundled template against its sample — byte for byte, through
the registry alone. The capability suites pin their arrangements against the
pre-rewrite functions; here the pin rides ``get_registry()``, so the next
edit to any bundled template or sample factory — or a new bundled key
without its golden — fails in one place, before any capability suite runs.
The key set itself is pinned both ways: a registration gone missing — its
module import or its ``register`` call swallowed by discovery — leaves a
golden without a prompt, and that is this file's failure to raise. A key
whose spec carries a contract must also pass it on its own bundled render:
the smoke is the first reader of a registration.
"""

import pytest

from app.kernel.prompts import get_registry, render_source


def _bundled(name: str) -> str:
    """The smoke render's include chain: a bundled key's template, unknown refused."""
    return get_registry().spec(name).template


# Today's sample renders — the bundled template against its sample factory —
# captured when the prompts docked. Provenance: writing's literal is the
# capability suite's own GOLDEN string plus the instruction sample block
# (W4 D5 — the legend shows the writer instruction the override may place);
# chat's sample rides that suite's QUESTION and first passage; the knowledge
# extract sample's body is the writing suite's BODY (not a shortened knowledge
# CHAPTER_BODY). A drift in either tier — template or factory — rots here first.
GOLDENS: dict[str, str] = {
    "chat.ask": (
        "Answer the question using only the sources below. Quote the passage that "
        "carries the answer verbatim, and do not add knowledge from outside them.\n"
        "\n"
        "Question: Wo war der Leuchtturm?\n"
        "\n"
        "Sources:\n"
        "SOURCE: Der Leuchtturm am Horizont war seit Jahren dunkel.\n"
    ),
    "knowledge.extract-entities": (
        "PURPOSE: extract-entities\n"
        "\n"
        "Extract the entities that appear in the chapter below. For each one judge "
        "a type — character|location|faction|object|system|timeline|event|generic — "
        "and write a one-sentence description of its role. "
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
        "Chapter: Ankunft\n"
        "Text:\n"
        "SOURCE: Der Nebel kam von See.\n"
    ),
    "knowledge.check-consistency": (
        "PURPOSE: check-consistency\n"
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
        "Mira (character)\n"
        "Haus (location)\n"
        "\n"
        "Chapter: Ankunft\n"
        "Text:\n"
        "SOURCE: Der Nebel kam von See.\n"
        "\n"
        "Chapter: Später\n"
        "Text:\n"
        "SOURCE: Mira betrat das alte Haus.\n"
    ),
    "knowledge.entity-interview": (
        "PURPOSE: entity-interview\n"
        "\n"
        "You are interviewing the writer to build one new entity for the novel "
        '"Der Nebel" in the genre Mystery.\n'
        "Ask exactly one question per turn — the most useful one for this entity — and\n"
        "never tell the writer what type of entity it is. When nothing useful is left\n"
        "to ask, say so in your reply and stop.\n"
        "\n"
        "Question tracks by entity type; use the one the TYPE line names:\n"
        "- name and role: what is the character called, and what part do they play?\n"
        "- appearance: what does the writer see when this character enters a scene?\n"
        "- want and fear: what do they want, and what are they afraid of?\n"
        "- how they speak: what do their words sound like on the page?\n"
        "- who they trust and who they oppose: who stands with them, who against?\n"
        "- what they hide: what do they keep from the other figures?\n"
        "\n"
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
        '"suggestion": string}. "slots" is the complete state so far: a key left out\n'
        'is untouched, a key given empty ("name": "", "content": "", "aliases": [],\n'
        '"tags": []) clears it, and a key with a value sets or extends it.\n'
        '"suggestion" is present only after no-idea. "relations" carries every\n'
        "proposal so far: leave the key out to keep the ones you were given, and give\n"
        "the full list so a relation you leave out is dropped.\n"
        "\n"
        "TYPE: character\n"
        "SLOTS: {}\n"
        "RELATIONS: []\n"
        "TURNS:\n"
        "ASSISTANT: Wie heißt die Figur, und welche Rolle spielt sie in der Geschichte?\n"
        "USER: Eine Wächterin am See; einen Namen habe ich noch nicht.\n"
        "ROSTER:\n"
        "Mira (character; Die Wanderin)\n"
        "Haus (location; Das Haus am See)\n"
        "Der Winter (event; Das Jahr ohne Sonne)\n"
        "REQUEST: answer\n"
    ),
    "writing.continuation": (
        "Novel: The Fog\n"
        "Chapter: Arrival\n"
        "\n"
        "Text so far:\n"
        "The fog came in from the lake.\n"
        "\n"
        "Referenced entities:\n"
        "### Mira (character)\n"
        "The wanderer.\n"
        "\n"
        "Previous chapters:\n"
        "### Origin\n"
        "Mira arrived.\n"
        "\n"
        "Style notes:\n"
        "Genre: Mystery\n"
        "Blurb: A year of fog.\n"
        "\n"
        "Continue the chapter in the same voice. Keep the language of the existing "
        "text. Return only the new text, without a heading or commentary."
        "\n\nWriter's instruction:\nLet Mira linger at the shore."
    ),
}


@pytest.mark.parametrize("key", get_registry().keys())
def test_every_bundled_prompt_renders_its_golden_sample(key: str) -> None:
    """The bundled template against the sample factory equals the pinned golden."""
    spec = get_registry().spec(key)
    golden = GOLDENS.get(key)
    assert golden is not None, f"the bundled prompt '{key}' carries no smoke golden yet"
    rendered = render_source(spec.template, spec.sample_variables(), include=_bundled)
    assert rendered == golden, (
        f"the bundled render of '{key}' drifted from its golden — "
        "its template or its sample factory changed"
    )
    if spec.contract is not None:
        assert spec.contract(rendered), f"the bundled render of '{key}' fails its contract"


def test_the_writing_sample_speaks_english_not_german() -> None:
    """The sample is the editor's legend in every catalog, so it carries no
    German prose: the English UI must not teach a German example."""
    sample = get_registry().spec("writing.continuation").sample_variables()
    text = "\n".join(str(value) for value in sample.values())
    for marker in ("ä", "ö", "ü", "ß", "Nebel", "Wanderin", "zögern"):
        assert marker not in text, f"the writing sample still carries German {marker!r}"


def test_the_registry_holds_exactly_the_pinned_keys() -> None:
    """The key set, pinned both ways: a registration discovery swallowed (a
    failed import, a refused duplicate) leaves a golden without a prompt; a
    new bundled key without its golden leaves a prompt without a pin."""
    assert set(get_registry().keys()) == set(GOLDENS)


@pytest.mark.parametrize("key", get_registry().keys())
def test_every_bundled_prompt_carries_its_live_assembly(key: str) -> None:
    """The live test rides the capability's own assembly; a key without one
    would refuse at the endpoint — a registration gap named here first."""
    assert get_registry().spec(key).assemble is not None
