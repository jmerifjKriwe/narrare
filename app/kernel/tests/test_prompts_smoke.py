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
# capability suite's own GOLDEN string; chat's sample rides that suite's
# QUESTION and first passage; the knowledge samples are the factories'
# shorter inputs over the same chapter texts. A drift in either tier —
# template or factory — rots here first.
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
    "writing.continuation": (
        "Novel: Der Nebel\n"
        "Chapter: Ankunft\n"
        "\n"
        "Text so far:\n"
        "Der Nebel kam von See.\n"
        "\n"
        "Referenced entities:\n"
        "### Mira (character)\n"
        "Die Wanderin.\n"
        "\n"
        "Previous chapters:\n"
        "### Ursprung\n"
        "Mira kam.\n"
        "\n"
        "Style notes:\n"
        "Genre: Mystery\n"
        "Blurb: Ein Nebeljahr.\n"
        "\n"
        "Continue the chapter in the same voice. Keep the language of the existing "
        "text. Return only the new text, without a heading or commentary."
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


def test_the_registry_holds_exactly_the_pinned_keys() -> None:
    """The key set, pinned both ways: a registration discovery swallowed (a
    failed import, a refused duplicate) leaves a golden without a prompt; a
    new bundled key without its golden leaves a prompt without a pin."""
    assert set(get_registry().keys()) == set(GOLDENS)
