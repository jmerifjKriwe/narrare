"""`writing.continuation` docks: the packers stay, the template arranges.

The golden pins today's prompt for a fixed rich input — every rewrite of the
arrangement must hold it byte for byte. The override tests then walk the
effective chain through the kernel ``render``: a novel-scoped row reorders
the sections, a frame too big for the immediate slice shrinks the tail, a
template whose glue grows as the tail shrinks is refused by name — never
truncated — and the sections themselves are never cut.
"""

import pytest

from app.capabilities.writing.prompts import continuation_prompt
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.context import ContextBudgets
from app.kernel.contracts.models import Chapter, Entity, Novel
from app.kernel.db.session import Session

BUDGETS = ContextBudgets(
    immediate_text=2000, referenced_entities=500, recent_chapters=400, style_hints=200
)
NOVEL_TITLE = "Der Nebel"
CHAPTER_TITLE = "Ankunft"
BODY = "Der Nebel kam von See."
ENTITIES = [Entity(name="Mira", type="character", content="Die Wanderin.", aliases=[])]
PREDECESSORS = [Chapter(title="Ursprung", position=0, body="Mira kam.")]
GENRE = "Mystery"
BLURB = "Ein Nebeljahr."

# Today's output for the rich input above, captured before the docking: the
# regression pin the rewrite must hold byte for byte.
GOLDEN = (
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
)


def test_the_bundled_arrangement_is_pinned_byte_for_byte() -> None:
    """The golden: today's arrangement, pinned against the docking."""
    prompt = continuation_prompt(
        budgets=BUDGETS,
        novel_title=NOVEL_TITLE,
        chapter_title=CHAPTER_TITLE,
        body=BODY,
        entities=ENTITIES,
        predecessors=PREDECESSORS,
        genre=GENRE,
        blurb=BLURB,
    )
    assert prompt == GOLDEN


async def test_the_bundled_chain_renders_the_pinned_prompt() -> None:
    """No override at either tier: the registry render is the pinned prompt."""
    from app.capabilities.writing.prompts import render_continuation

    async with Session() as session:
        prompt = await render_continuation(
            session,
            LOCAL_USER_ID,
            None,
            budgets=BUDGETS,
            novel_title=NOVEL_TITLE,
            chapter_title=CHAPTER_TITLE,
            body=BODY,
            entities=ENTITIES,
            predecessors=PREDECESSORS,
            genre=GENRE,
            blurb=BLURB,
        )
    assert prompt == GOLDEN


async def test_a_novel_override_reorders_the_sections() -> None:
    """The novel's row is the source: its arrangement is what the caller gets."""
    from app.capabilities.writing.prompts import render_continuation
    from app.kernel.prompts.models import PromptTemplateRepository

    override = (
        "{{ style_section }}"
        "{{ entities_section }}"
        "Novel: {{ novel_title }}\nChapter: {{ chapter_title }}\n\n"
        "{{ predecessors_section }}"
        "Text so far:\n{{ tail }}"
    )
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title=NOVEL_TITLE)
        session.add(novel)
        # The id exists only after a flush — saving with it before would write
        # the GLOBAL row and this test would pass through the global fallback
        # (the mistake test_prompts_knowledge documents at its own flush).
        await session.flush()
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(
            "writing.continuation", override, novel.id
        )
        await session.commit()
        prompt = await render_continuation(
            session,
            LOCAL_USER_ID,
            novel.id,
            budgets=BUDGETS,
            novel_title=NOVEL_TITLE,
            chapter_title=CHAPTER_TITLE,
            body=BODY,
            entities=ENTITIES,
            predecessors=PREDECESSORS,
            genre=GENRE,
            blurb=BLURB,
        )
    assert prompt.startswith("Style notes:\nGenre: Mystery\nBlurb: Ein Nebeljahr.\n\n")
    assert prompt.index("Referenced entities:") < prompt.index("Novel: Der Nebel")
    assert prompt.index("Novel: Der Nebel") < prompt.index("Previous chapters:")
    # the sections ride whole, wherever the override puts them
    assert "### Mira (character)\nDie Wanderin." in prompt
    assert "### Ursprung\nMira kam." in prompt
    assert prompt.endswith(BODY)
    # The override lives on the novel's row only: without a novel scope the
    # chain answers bundled — a save that wrote the global row instead fails
    # here, so this test bites for the tier it names.
    async with Session() as session:
        global_prompt = await render_continuation(
            session,
            LOCAL_USER_ID,
            None,
            budgets=BUDGETS,
            novel_title=NOVEL_TITLE,
            chapter_title=CHAPTER_TITLE,
            body=BODY,
            entities=ENTITIES,
            predecessors=PREDECESSORS,
            genre=GENRE,
            blurb=BLURB,
        )
    assert global_prompt == GOLDEN


async def test_a_huge_frame_shrinks_the_tail_and_holds_the_total() -> None:
    """A long instruction eats the immediate slice: the tail shrinks by the
    measured frame, the sections stay whole, and the result never exceeds the
    four slices together."""
    from app.capabilities.writing.prompts import render_continuation
    from app.kernel.prompts import render_source
    from app.kernel.prompts.models import PromptTemplateRepository

    instruction = "W" * 900
    override = (
        "Novel: {{ novel_title }}\nChapter: {{ chapter_title }}\n\n"
        "Text so far:\n{{ tail }}\n\n"
        "{{ entities_section }}{{ predecessors_section }}{{ style_section }}" + instruction
    )

    def no_includes(key: str) -> str:
        raise KeyError(key)

    empty = {
        "novel_title": NOVEL_TITLE,
        "chapter_title": CHAPTER_TITLE,
        "tail": "",
        "entities_section": "",
        "predecessors_section": "",
        "style_section": "",
    }
    probe = render_source(override, empty, include=no_includes)
    # the frame, per the design: the render beyond the sections and the tail —
    # with both empty, the probe itself
    frame = len(probe)
    body = "Z" * 5000

    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(
            "writing.continuation", override, None
        )
        await session.commit()
        prompt = await render_continuation(
            session,
            LOCAL_USER_ID,
            None,
            budgets=BUDGETS,
            novel_title=NOVEL_TITLE,
            chapter_title=CHAPTER_TITLE,
            body=body,
            entities=ENTITIES,
            predecessors=PREDECESSORS,
            genre=GENRE,
            blurb=BLURB,
        )
    assert prompt.count("Z") == BUDGETS.immediate_text - frame
    assert instruction in prompt
    assert "### Mira (character)\nDie Wanderin." in prompt
    assert "### Ursprung\nMira kam." in prompt
    assert "Blurb: Ein Nebeljahr." in prompt
    assert len(prompt) <= (
        BUDGETS.immediate_text
        + BUDGETS.referenced_entities
        + BUDGETS.recent_chapters
        + BUDGETS.style_hints
    )


async def test_glue_that_grows_as_the_tail_shrinks_is_refused_by_name() -> None:
    """A frame that only fits while the tail is long cannot be truncated into
    fitting: the render is refused `budget`, the sections untouched."""
    from app.capabilities.writing.prompts import render_continuation
    from app.kernel.prompts import PromptRenderError
    from app.kernel.prompts.models import PromptTemplateRepository

    grow = (
        "{% if tail|length > 100 %}" + "X" * 150 + "{{ tail }}"
        "{% else %}" + "Y" * 300 + "{{ tail }}"
        "{% endif %}"
    )
    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(
            "writing.continuation", grow, None
        )
        await session.commit()
        with pytest.raises(PromptRenderError) as raised:
            await render_continuation(
                session,
                LOCAL_USER_ID,
                None,
                budgets=ContextBudgets(
                    immediate_text=200, referenced_entities=0, recent_chapters=0, style_hints=0
                ),
                novel_title="",
                chapter_title="",
                body="B" * 1000,
                entities=(),
                predecessors=(),
                genre=None,
                blurb=None,
            )
    assert raised.value.reason == "budget"


async def test_the_tail_shrinks_by_the_frame_the_override_measures() -> None:
    """A 500-character instruction and a full chapter: the slice stays filled,
    the tail is what the measured frame leaves of it — never the body's front."""
    from app.capabilities.writing.prompts import render_continuation
    from app.kernel.prompts import render_source
    from app.kernel.prompts.models import PromptTemplateRepository

    instruction = "Y" * 500
    override = (
        "Novel: {{ novel_title }}\nChapter: {{ chapter_title }}\n\n"
        "Text so far:\n{{ tail }}\n\n"
        "{{ entities_section }}{{ predecessors_section }}{{ style_section }}" + instruction
    )

    def no_includes(key: str) -> str:
        raise KeyError(key)

    empty = {
        "novel_title": NOVEL_TITLE,
        "chapter_title": CHAPTER_TITLE,
        "tail": "",
        "entities_section": "",
        "predecessors_section": "",
        "style_section": "",
    }
    probe = render_source(override, empty, include=no_includes)
    frame = len(probe)  # the render beyond the sections and the tail, both empty here
    assert 0 < 1000 - frame < 3000  # a tail survives, cut by the frame alone

    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(
            "writing.continuation", override, None
        )
        await session.commit()
        prompt = await render_continuation(
            session,
            LOCAL_USER_ID,
            None,
            budgets=ContextBudgets(
                immediate_text=1000, referenced_entities=0, recent_chapters=0, style_hints=0
            ),
            novel_title=NOVEL_TITLE,
            chapter_title=CHAPTER_TITLE,
            body="Z" * 3000,
            entities=(),
            predecessors=(),
            genre=None,
            blurb=None,
        )
    tail = "Z" * (1000 - frame)
    assert prompt == (
        f"Novel: {NOVEL_TITLE}\nChapter: {CHAPTER_TITLE}\n\nText so far:\n{tail}\n\n{instruction}"
    )


async def test_a_refused_override_ends_the_stream_with_the_one_error_frame(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A render the chain refuses is the one error frame — no call, no audit row.

    The refusal happens where the budget pair is refused, before any provider
    is touched: the stream ends the way a lost key ends it, and the log names
    the refusal the way the budget branch names its own.
    """
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text as sql_text

    from app.api.main import app
    from app.kernel.prompts.models import PromptTemplateRepository

    # Glue that grows as the tail shrinks: the if-branch already fills the
    # default tier's immediate slice, the else-branch exceeds it whole.
    grow = "{% if tail %}" + "X" * 20_000 + "{{ tail }}{% else %}" + "Y" * 30_000 + "{% endif %}"
    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(
            "writing.continuation", grow, None
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
        chapter = await client.post(
            f"/api/writing/novels/{novel.json()['id']}/chapters", json={"title": "Ankunft"}
        )
        chapter_id = chapter.json()["id"]
        await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": "B" * 200})
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")

    assert response.status_code == 200
    assert response.text == "event: error\ndata: {}\n\n"
    async with Session() as session:
        assert await session.scalar(sql_text("SELECT count(*) FROM llm_calls")) == 0
    refusals = [
        record for record in caplog.records if record.getMessage() == "continuation prompt refused"
    ]
    assert len(refusals) == 1
    assert refusals[0].exc_info is not None
