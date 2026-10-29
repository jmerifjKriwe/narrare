"""`chat.ask` docks: the sources stay marked.

The golden pins today's prompt for a fixed question and two passages — every
rewrite must hold it byte for byte. The override tests then walk the effective
chain: a global override re-voices the frame, the marked source line survives
it and the fake still quotes the passage; a render that loses the marker is
what the contract refuses.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

from app.capabilities.chat.prompts import chat_prompt
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.llm import SOURCE_PREFIX
from app.kernel.retrieval import Passage

if TYPE_CHECKING:
    import pytest

QUESTION = "Wo war der Leuchtturm?"
FIRST_PASSAGE = "Der Leuchtturm am Horizont war seit Jahren dunkel."
SECOND_PASSAGE = "Mira betrat das alte Haus am See."


def _passage(text: str) -> Passage:
    return Passage(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_title="Notizen",
        text=text,
        score=0.1,
    )


PASSAGES = [_passage(FIRST_PASSAGE), _passage(SECOND_PASSAGE)]

# Today's output for the input above, captured before the docking: the
# regression pin the rewrite must hold byte for byte.
GOLDEN = (
    "Answer the question using only the sources below. Quote the passage that "
    "carries the answer verbatim, and do not add knowledge from outside them.\n"
    "\n"
    f"Question: {QUESTION}\n"
    "\n"
    "Sources:\n"
    f"{SOURCE_PREFIX}{FIRST_PASSAGE}\n"
    f"{SOURCE_PREFIX}{SECOND_PASSAGE}\n"
)


def test_the_bundled_prompt_is_pinned_byte_for_byte() -> None:
    """The golden: today's arrangement, pinned against the docking."""
    assert chat_prompt(question=QUESTION, passages=PASSAGES) == GOLDEN


async def test_the_bundled_chain_renders_the_pinned_prompt() -> None:
    """No override at either tier: the registry render is the pinned prompt."""
    from app.capabilities.chat.prompts import CHAT_KEY, sources_block
    from app.kernel.db.session import Session
    from app.kernel.prompts import render

    async with Session() as session:
        prompt = await render(
            session,
            LOCAL_USER_ID,
            CHAT_KEY,
            {"question": QUESTION, "sources": sources_block(PASSAGES)},
        )
    assert prompt == GOLDEN


def test_the_key_is_registered_global_only() -> None:
    """chat.ask carries no novel scope; the contract rides the spec."""
    from app.capabilities.chat.prompts import CHAT_KEY, chat_contract
    from app.kernel.prompts import get_registry

    spec = get_registry().spec(CHAT_KEY)
    assert spec.novel_scopable is False
    assert spec.contract is chat_contract


async def test_a_global_override_revoices_the_frame_and_the_fake_still_quotes_the_passage() -> None:
    """The override owns the frame; the marked source line survives it.

    The rendered prompt drives the fake provider the way the kernel tests do:
    its answer quotes the passage, so a re-voice cannot strand retrieval.
    """
    from app.capabilities.chat.prompts import CHAT_KEY
    from app.capabilities.chat.service import ChatService
    from app.kernel.contracts.models import Chunk, Document
    from app.kernel.db.session import Session
    from app.kernel.embeddings import FakeEmbeddingProvider
    from app.kernel.llm.contract import CompletionRequest, Delta
    from app.kernel.llm.fake import FakeProvider
    from app.kernel.prompts.models import PromptTemplateRepository

    override = (
        "Answer strictly from the sources.\n\n"
        "Asked: {{ question }}\n\n"
        "The sources:\n{{ sources }}\n"
    )
    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(CHAT_KEY, override, None)
        await session.commit()
        # One document, one chunk: retrieval returns exactly this passage.
        [vector] = await FakeEmbeddingProvider().embed([FIRST_PASSAGE])
        document = Document(user_id=LOCAL_USER_ID, title="Notizen", embedding_width=len(vector))
        session.add(document)
        await session.flush()
        session.add(
            Chunk(
                user_id=LOCAL_USER_ID,
                document_id=document.id,
                position=0,
                text=FIRST_PASSAGE,
                embedding=vector,
            )
        )
        await session.commit()
        prompt, passages = await ChatService(
            session, LOCAL_USER_ID, FakeEmbeddingProvider()
        ).prepare(QUESTION, 5)

    assert prompt.startswith("Answer strictly from the sources.")
    assert SOURCE_PREFIX + FIRST_PASSAGE in prompt
    assert [passage.text for passage in passages] == [FIRST_PASSAGE]
    events = [event async for event in FakeProvider().stream(CompletionRequest.user(prompt))]
    answer = "".join(event.text for event in events if isinstance(event, Delta))
    assert FIRST_PASSAGE in answer


def test_the_contract_refuses_a_render_without_the_source_marker() -> None:
    """A render that lost the marked sources is refused; the pinned one passes."""
    from app.capabilities.chat.prompts import chat_contract
    from app.kernel.prompts import render_source

    def no_includes(key: str) -> str:
        raise KeyError(key)

    dropped = render_source("Asked: {{ question }}", {"question": QUESTION}, include=no_includes)
    assert chat_contract(dropped) is False
    assert chat_contract(GOLDEN) is True


def test_the_sample_renders_through_the_contract() -> None:
    """The sample the editor's legend renders is a valid prompt by the contract."""
    from app.capabilities.chat.prompts import CHAT_TEMPLATE, chat_contract, sample_variables
    from app.kernel.prompts import render_source

    def no_includes(key: str) -> str:
        raise KeyError(key)

    rendered = render_source(CHAT_TEMPLATE, sample_variables(), include=no_includes)
    assert "Question: Wo war der Leuchtturm?" in rendered
    assert SOURCE_PREFIX in rendered
    assert chat_contract(rendered) is True


async def test_a_refused_override_ends_the_stream_with_the_one_error_frame(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A render the chain refuses is the one error frame — no call, no audit row.

    The refusal happens where a dead provider's lost key is refused, before any
    provider is touched: the stream ends the same way, and the log names the
    refusal the way the resolution branch names its own.
    """
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text as sql_text

    from app.api.main import app
    from app.capabilities.chat.prompts import CHAT_KEY
    from app.kernel.db.session import Session
    from app.kernel.prompts.models import PromptTemplateRepository

    override = "Asked: {{ question }} {{ ghost }}"  # an unknown variable: refused
    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(CHAT_KEY, override, None)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/ask", json={"question": QUESTION})

    assert response.status_code == 200
    assert response.text == "event: error\ndata: {}\n\n"
    async with Session() as session:
        assert await session.scalar(sql_text("SELECT count(*) FROM llm_calls")) == 0
    refusals = [record for record in caplog.records if record.getMessage() == "chat prompt refused"]
    assert len(refusals) == 1
    assert refusals[0].exc_info is not None
