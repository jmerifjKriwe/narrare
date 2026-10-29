"""`knowledge.extract-entities` and `knowledge.check-consistency` dock: purposes stay marked.

The goldens pin today's prompts for fixed inputs — every rewrite of the
arrangement must hold them byte for byte. The override tests then walk the
effective chain: a global override re-voices the frame, the marked purpose
line and chapter survive it and the fake still derives its answer from the
marked text; a render that loses the purpose line or the marked payload is
what the contract refuses — content-bound, not a prefix check.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.capabilities.knowledge.prompts import consistency_prompt, extraction_prompt
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.llm import PURPOSE_PREFIX

pytestmark = pytest.mark.timeout(60)

CHAPTER_TITLE = "Ankunft"
CHAPTER_BODY = (
    "Mira betrat das alte Haus am See. Der Leuchtturm schwieg, und Nebel zog über das Dorf."
)
LATER_TITLE = "Später"
LATER_BODY = "Der Nebel hob sich, und Mira sah das Haus am See."
CANON = [("Mira", "character"), ("Haus", "location")]
CHAPTERS = [(CHAPTER_TITLE, CHAPTER_BODY), (LATER_TITLE, LATER_BODY)]

# The fake's derivation for CHAPTER_BODY: every distinct capitalized word, in
# the vocabulary's order — the same answer the un-overridden prompt earns.
DERIVED_NAMES = ["Mira", "Haus", "See", "Der", "Leuchtturm", "Nebel", "Dorf"]

# Today's outputs for the inputs above, captured before the docking: the
# regression pins the rewrite must hold byte for byte.
EXTRACTION_GOLDEN = (
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
    f"Chapter: {CHAPTER_TITLE}\n"
    f"Text:\nSOURCE: {CHAPTER_BODY}\n"
)

CONSISTENCY_GOLDEN = (
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
    f"Chapter: {CHAPTER_TITLE}\n"
    f"Text:\nSOURCE: {CHAPTER_BODY}\n"
    "\n"
    f"Chapter: {LATER_TITLE}\n"
    f"Text:\nSOURCE: {LATER_BODY}\n"
)


def _render(source: str, variables: dict[str, object]) -> str:
    """The offline render the contract tests drive; the bundled template includes nothing."""

    from app.kernel.prompts import render_source

    def no_includes(key: str) -> str:
        raise KeyError(key)

    return render_source(source, variables, include=no_includes)


def _client() -> AsyncClient:
    """Create an HTTP client that drives the real application through ASGI."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _run_lane_once() -> bool:
    """One claim of the lane, the way the api app's task would run it."""
    from app.capabilities.knowledge.jobs import handlers
    from app.kernel.db.session import Session
    from app.kernel.jobs.worker import Worker

    return await Worker(Session, handlers).run_once()


async def _enqueue_extraction(client: AsyncClient, novel_id: str, chapter_id: str) -> str:
    """Enqueue one extraction run, asserting the contract's 202."""
    response = await client.post(
        f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id}
    )
    assert response.status_code == 202
    return response.json()["job_id"]


async def _enqueue_consistency(client: AsyncClient, novel_id: str) -> str:
    """Enqueue one consistency run, asserting the contract's 202."""
    response = await client.post(f"/api/knowledge/consistency/{novel_id}")
    assert response.status_code == 202
    return response.json()["job_id"]


async def _chapter(client: AsyncClient) -> tuple[str, str]:
    """A novel with one written chapter carrying CHAPTER_BODY, both the caller's own."""
    novel = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
    novel_id = novel.json()["id"]
    chapter = await client.post(
        f"/api/writing/novels/{novel_id}/chapters", json={"title": CHAPTER_TITLE}
    )
    chapter_id = chapter.json()["id"]
    await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": CHAPTER_BODY})
    return novel_id, chapter_id


def test_the_bundled_extraction_prompt_is_pinned_byte_for_byte() -> None:
    """The extraction golden: today's arrangement, pinned against the docking."""
    assert extraction_prompt(chapter_title=CHAPTER_TITLE, body=CHAPTER_BODY) == EXTRACTION_GOLDEN


def test_the_bundled_consistency_prompt_is_pinned_byte_for_byte() -> None:
    """The consistency golden: today's arrangement, pinned against the docking."""
    assert consistency_prompt(entities=CANON, chapters=CHAPTERS) == CONSISTENCY_GOLDEN


async def test_the_bundled_chain_renders_the_pinned_extraction_prompt() -> None:
    """No override at either tier: the registry render is the pinned prompt."""
    from app.capabilities.knowledge.prompts import EXTRACTION_KEY, extraction_variables
    from app.kernel.db.session import Session
    from app.kernel.prompts import render

    async with Session() as session:
        prompt = await render(
            session,
            LOCAL_USER_ID,
            EXTRACTION_KEY,
            extraction_variables(chapter_title=CHAPTER_TITLE, body=CHAPTER_BODY),
        )
    assert prompt == EXTRACTION_GOLDEN


async def test_the_bundled_chain_renders_the_pinned_consistency_prompt() -> None:
    """No override at either tier: the registry render is the pinned prompt."""
    from app.capabilities.knowledge.prompts import CONSISTENCY_KEY, consistency_variables
    from app.kernel.db.session import Session
    from app.kernel.prompts import render

    async with Session() as session:
        prompt = await render(
            session,
            LOCAL_USER_ID,
            CONSISTENCY_KEY,
            consistency_variables(entities=CANON, chapters=CHAPTERS),
        )
    assert prompt == CONSISTENCY_GOLDEN


def test_both_keys_are_registered_novel_scopable() -> None:
    """Both knowledge keys carry a novel scope and a contract, per the plan."""
    from app.capabilities.knowledge.prompts import (
        CONSISTENCY_KEY,
        EXTRACTION_KEY,
        consistency_contract,
        extraction_contract,
    )
    from app.kernel.prompts import get_registry

    registry = get_registry()
    extraction = registry.spec(EXTRACTION_KEY)
    consistency = registry.spec(CONSISTENCY_KEY)
    assert extraction.novel_scopable is True
    assert consistency.novel_scopable is True
    assert extraction.contract is extraction_contract
    assert consistency.contract is consistency_contract


async def test_a_novel_override_revoices_the_consistency_frame_and_keeps_the_chapters() -> None:
    """The novel's row outranks the global tier: its arrangement is what the
    caller gets, with the marked purpose line and both marked chapters riding
    it."""
    from app.capabilities.knowledge.prompts import CONSISTENCY_KEY, consistency_variables
    from app.kernel.contracts.models import Novel
    from app.kernel.db.session import Session
    from app.kernel.prompts import render
    from app.kernel.prompts.models import PromptTemplateRepository

    novel_override = (
        "Read the two chapters as one story, the novel's way.\n\n"
        "{{ purpose_line }}\n\n"
        "Canon:\n{{ grounding }}\n\n"
        "{{ chapters }}\n"
    )
    global_override = (
        "Read the two chapters as one story, the global way.\n\n"
        "{{ purpose_line }}\n\n"
        "Canon:\n{{ grounding }}\n\n"
        "{{ chapters }}\n"
    )
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Der Nebel")
        session.add(novel)
        # The row's key exists only after a flush: a pending Novel carries no
        # id yet, and a save with novel_id=None would write the global tier —
        # the exact slip a novel-scope test must not make silently.
        await session.flush()
        repository = PromptTemplateRepository(session, LOCAL_USER_ID)
        await repository.save(CONSISTENCY_KEY, global_override, None)
        await repository.save(CONSISTENCY_KEY, novel_override, novel.id)
        await session.commit()
        prompt = await render(
            session,
            LOCAL_USER_ID,
            CONSISTENCY_KEY,
            consistency_variables(entities=CANON, chapters=CHAPTERS),
            novel_id=novel.id,
        )
    assert prompt.startswith("Read the two chapters as one story, the novel's way.")
    assert "the global way" not in prompt
    assert "PURPOSE: check-consistency" in prompt
    assert "Mira (character)" in prompt
    assert prompt.index("Mira (character)") < prompt.index("Chapter:")
    assert f"SOURCE: {CHAPTER_BODY}" in prompt
    assert f"SOURCE: {LATER_BODY}" in prompt


async def test_a_global_override_revoices_the_frame_and_the_fake_still_derives_the_entities() -> (
    None
):
    """The heart: a re-voiced extraction prompt still answers through the fake.

    The override owns the frame, `{{ purpose_line }}` and `{{ sources }}`
    ride it; the job runs the real lane end to end and the suggestions are
    the fake's derivation from the marked chapter — a re-voice cannot strand
    the extraction. The audit row's `prompt_text` proves the override reached
    the provider boundary.
    """
    from app.kernel.db.session import Session
    from app.kernel.prompts.models import PromptTemplateRepository

    override = (
        "List every entity that appears in the chapter text below, each with "
        "its type, as the JSON the marked purpose names.\n\n"
        "{{ purpose_line }}\n\n"
        "Chapter: {{ chapter_title }}\n"
        "The chapter text:\n{{ sources }}\n"
    )
    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(
            "knowledge.extract-entities", override, None
        )
        await session.commit()

    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)
        job_id = await _enqueue_extraction(client, novel_id, chapter_id)
        assert await _run_lane_once() is True
        done = (await client.get(f"/api/jobs/{job_id}")).json()
        pending = await client.get(f"/api/knowledge/novels/{novel_id}/suggestions")

    assert done["status"] == "done"
    assert done["result"] == {"suggestions": len(DERIVED_NAMES), "truncated": False}
    assert [suggestion["name"] for suggestion in pending.json()] == DERIVED_NAMES

    async with Session() as session:
        row = (await session.execute(text("SELECT prompt_text, task_key FROM llm_calls"))).one()
    assert row.task_key == "knowledge.extract-entities"
    assert row.prompt_text is not None
    assert row.prompt_text.startswith("List every entity")
    assert "PURPOSE: extract-entities" in row.prompt_text
    assert f"SOURCE: {CHAPTER_BODY}" in row.prompt_text


def test_the_extraction_contract_refuses_a_render_that_loses_purpose_or_payload() -> None:
    """The contract is content-bound: purpose line and marked payload must ride.

    A re-voiced frame that keeps both passes; dropping the purpose line,
    renaming the purpose, dropping the chapter, or keeping the marker as a
    bare `SOURCE: ` line — the ruling's case — is refused.
    """
    from app.capabilities.knowledge.prompts import (
        extraction_contract,
        sample_variables_extraction,
    )

    sample = sample_variables_extraction()
    # a re-voiced frame on real override text: both variables ride — accepted
    voiced = _render(
        "Extract every entity.\n\n{{ purpose_line }}\n\nChapter: {{ chapter_title }}\n"
        "{{ sources }}\n",
        dict(sample),
    )
    assert extraction_contract(voiced) is True

    # the purpose line dropped: the fake loses the answer shape
    dropped = _render("Chapter: {{ chapter_title }}\nText:\n{{ sources }}\n", dict(sample))
    assert extraction_contract(dropped) is False
    # the purpose renamed: the fake would fall to its default prose
    renamed = dict(sample, purpose_line=f"{PURPOSE_PREFIX}check-consistency")
    assert extraction_contract(_render("{{ purpose_line }}\n\n{{ sources }}\n", renamed)) is False
    # the chapter dropped whole
    assert (
        extraction_contract(
            _render("{{ purpose_line }}\nChapter: {{ chapter_title }}\n", dict(sample))
        )
        is False
    )
    # the ruling's case: a bare marker without the body behind it
    bare = _render(
        "{{ purpose_line }}\n\nChapter: {{ chapter_title }}\nText:\nSOURCE: \n",
        dict(sample),
    )
    assert extraction_contract(bare) is False


def test_the_consistency_contract_refuses_a_render_that_loses_purpose_or_payload() -> None:
    """The same content-bound pair for the check: canon and chapters must ride."""
    from app.capabilities.knowledge.prompts import (
        consistency_contract,
        sample_variables_consistency,
    )

    sample = sample_variables_consistency()
    voiced = _render(
        "Find the contradictions.\n\n{{ purpose_line }}\n\nCanon:\n{{ grounding }}\n\n"
        "{{ chapters }}\n",
        dict(sample),
    )
    assert consistency_contract(voiced) is True

    dropped = _render("Canon:\n{{ grounding }}\n\n{{ chapters }}\n", dict(sample))
    assert consistency_contract(dropped) is False
    renamed = dict(sample, purpose_line=f"{PURPOSE_PREFIX}extract-entities")
    assert consistency_contract(_render("{{ purpose_line }}\n\n{{ chapters }}\n", renamed)) is False
    assert (
        consistency_contract(_render("{{ purpose_line }}\nCanon:\n{{ grounding }}\n", dict(sample)))
        is False
    )
    bare = _render(
        "{{ purpose_line }}\n\nCanon:\n{{ grounding }}\n\nChapter: Ankunft\nText:\nSOURCE: \n",
        dict(sample),
    )
    assert consistency_contract(bare) is False


def test_the_samples_render_through_the_contracts() -> None:
    """The samples the editor's legend renders are valid prompts by the contracts."""
    from app.capabilities.knowledge.prompts import (
        CONSISTENCY_TEMPLATE,
        EXTRACTION_TEMPLATE,
        consistency_contract,
        extraction_contract,
        sample_variables_consistency,
        sample_variables_extraction,
    )

    rendered = _render(EXTRACTION_TEMPLATE, sample_variables_extraction())
    assert "PURPOSE: extract-entities" in rendered
    assert "SOURCE: " in rendered
    assert extraction_contract(rendered) is True

    rendered = _render(CONSISTENCY_TEMPLATE, sample_variables_consistency())
    assert "PURPOSE: check-consistency" in rendered
    assert "SOURCE: " in rendered
    assert consistency_contract(rendered) is True


async def test_a_refused_render_fails_the_job_row_and_writes_nothing() -> None:
    """A render the chain refuses fails the job the way a malformed answer does.

    No provider is resolved and no call is made: the refusal happens where
    the prompt is built, and the row carries the named reason — the lane's
    own record, not a silent bundled swap.
    """
    from app.kernel.db.session import Session
    from app.kernel.prompts.models import PromptTemplateRepository

    override = "Asked for: {{ ghost }}"  # an unknown variable: refused
    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(
            "knowledge.extract-entities", override, None
        )
        await session.commit()

    async with _client() as client:
        novel_id, chapter_id = await _chapter(client)
        job_id = await _enqueue_extraction(client, novel_id, chapter_id)

        # The failure earns exactly one re-run (MAX_ATTEMPTS = 2), then fails.
        assert await _run_lane_once() is True
        assert await _run_lane_once() is True
        assert await _run_lane_once() is False  # nothing queued anymore

        job = (await client.get(f"/api/jobs/{job_id}")).json()
        assert job["status"] == "failed"
        assert job["error"] is not None
        assert "undefined-variable" in job["error"]
        assert job["result"] is None

    async with Session() as session:
        suggestions = await session.scalar(text("SELECT count(*) FROM entity_suggestions"))
        calls = await session.scalar(text("SELECT count(*) FROM llm_calls"))
    assert suggestions == 0
    assert calls == 0  # a failed job writes no audit row (D3)


async def test_a_refused_consistency_render_fails_the_job_row_and_writes_nothing() -> None:
    """The symmetric pin for the check: a render the chain refuses fails the
    job the way a malformed answer does — same uncaught-render shape in the
    handler, same failed, named row, nothing written.

    The novel carries one checkable chapter, so a group exists and the render
    actually runs; the provider is resolved before the render loop but is
    never asked — no call, no audit row.
    """
    from app.kernel.db.session import Session
    from app.kernel.prompts.models import PromptTemplateRepository

    override = "Checked for: {{ ghost }}"  # an unknown variable: refused
    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(
            "knowledge.check-consistency", override, None
        )
        await session.commit()

    async with _client() as client:
        novel_id, _chapter_id = await _chapter(client)
        job_id = await _enqueue_consistency(client, novel_id)

        # The failure earns exactly one re-run (MAX_ATTEMPTS = 2), then fails.
        assert await _run_lane_once() is True
        assert await _run_lane_once() is True
        assert await _run_lane_once() is False  # nothing queued anymore

        job = (await client.get(f"/api/jobs/{job_id}")).json()
        assert job["status"] == "failed"
        assert job["error"] is not None
        assert "undefined-variable" in job["error"]
        assert job["result"] is None

    async with Session() as session:
        findings = await session.scalar(text("SELECT count(*) FROM consistency_findings"))
        calls = await session.scalar(text("SELECT count(*) FROM llm_calls"))
    assert findings == 0
    assert calls == 0  # a failed job writes no audit row (D3)
