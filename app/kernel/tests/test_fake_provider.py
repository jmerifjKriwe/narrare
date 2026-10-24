"""The fake provider's answer shapes: the purpose marker decides.

The fake is a catalog entry, not a test branch, so its branching is contract:
a prompt that declares its purpose in a marked line gets the answer that
purpose contracts, derived from the marked passages — and an unmarked prompt
keeps the chat behavior byte-identical, which the chat suite proves end to
end. These tests pin the branching itself, at the provider boundary.
"""

import json

from app.kernel.llm import FakeProvider


async def _answer(prompt: str) -> str:
    """The whole completion, joined — what a consumer accumulates on the wire."""
    pieces: list[str] = []
    async for piece in FakeProvider().stream(prompt):
        pieces.append(piece)
    return "".join(pieces)


async def test_an_extraction_prompt_proposes_entities_from_its_passage() -> None:
    prompt = (
        "PURPOSE: extract-entities\n\n"
        "Extract the entities of the chapter.\n\n"
        "Chapter: Ankunft\n"
        "Text:\n"
        "SOURCE: Mira betrat das alte Haus am See.\n"
    )

    assert json.loads(await _answer(prompt)) == [
        {"name": "Mira", "kind": "character", "description": "Mira appears in the chapter."},
        {"name": "Haus", "kind": "place", "description": "Haus appears in the chapter."},
        {"name": "See", "kind": "thing", "description": "See appears in the chapter."},
    ]


async def test_a_multiline_passage_is_read_whole() -> None:
    # A chapter body spans lines; the passage runs from its marker to the next
    # one, so the derivation sees every line — not just the marked first.
    prompt = (
        "PURPOSE: extract-entities\n\n"
        "Extract the entities of the chapter.\n\n"
        "Chapter: Ankunft\n"
        "Text:\n"
        "SOURCE: Mira kam.\n"
        "Haus und See schliefen.\n"
    )

    answer = json.loads(await _answer(prompt))
    assert [entity["name"] for entity in answer] == ["Mira", "Haus", "See"]


async def test_a_consistency_prompt_gets_one_finding_per_contradicted_name() -> None:
    # The contradiction spans the two chapters: Mira carries two numbers.
    prompt = (
        "PURPOSE: check-consistency\n\n"
        "Find the contradictions.\n\n"
        "Chapter: Ankunft\n"
        "Text:\n"
        "SOURCE: Mira ist 34 Jahre alt.\n\n"
        "Chapter: Später\n"
        "Text:\n"
        "SOURCE: Später steht geschrieben, Mira ist 37.\n"
    )

    assert json.loads(await _answer(prompt)) == [
        {
            "summary": "Mira: 34 vs. 37",
            "detail": '"Mira ist 34" vs. "Mira ist 37"',
        }
    ]


async def test_a_name_with_one_reading_is_no_finding() -> None:
    # Two chapters, one number for Mira: the readings agree, so the honest
    # answer is the empty array the prompt promises is valid.
    prompt = (
        "PURPOSE: check-consistency\n\n"
        "Find the contradictions.\n\n"
        "Chapter: Ankunft\n"
        "Text:\n"
        "SOURCE: Mira ist 34 Jahre alt.\n\n"
        "Chapter: Später\n"
        "Text:\n"
        "SOURCE: Mira ist 34, wie zuvor.\n"
    )

    assert json.loads(await _answer(prompt)) == []


async def test_an_unmarked_prompt_keeps_the_chat_answer() -> None:
    # No purpose line: the fixed continuation, byte-identical — the chat
    # prompts never carry one, and their behavior must not move.
    assert await _answer("Erzähl weiter.") == "".join(FakeProvider.CHUNKS)

    with_source = (
        "Answer the question using only the sources below.\n\n"
        "Sources:\n"
        "SOURCE: Der Leuchtturm war dunkel.\n"
    )
    assert await _answer(with_source) == "Der Leuchtturm war dunkel."


async def test_an_unmarked_prompt_with_many_sources_quotes_the_first() -> None:
    # The chat shape with several retrieved passages: the first one is the
    # answer, the way it was when the fake quoted a single source.
    prompt = "Sources:\nSOURCE: Erste Passage.\nSOURCE: Zweite Passage.\n"

    assert await _answer(prompt) == "Erste Passage."


async def test_the_json_phrase_no_longer_decides_the_answer_shape() -> None:
    # The retired sniff: asking for "a JSON array" in prose is not a contract
    # anymore. An unmarked prompt gets the default answer even when its
    # instruction carries the phrase — only the purpose marker branches.
    prompt = (
        "Answer with a JSON array of objects and nothing else.\n\n"
        "Text:\n"
        "SOURCE: Mira betrat das Haus.\n"
    )

    answer = await _answer(prompt)

    assert answer == "Mira betrat das Haus."  # the source-quote default, not JSON
