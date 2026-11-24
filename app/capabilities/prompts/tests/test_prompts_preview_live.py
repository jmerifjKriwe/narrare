"""The preview and the live test: the editor's two seams onto the wire.

The preview renders at sample scope through the save gate's sandbox — no
model call, nothing persisted — and answers the rendered text beside the
provenance of every variable (which the draft reads) and the diagnostics
(the contract's verdict included). A draft that cannot render is refused by
the render's own reason, exactly what the save would say.

The live test rides the capability's real context assembly — the scene the
writer last touched, the chapter's prose, the retrieved passages — and the
key's task assignment; the editor draft passes the save gate's sandbox
before any provider call and is never persisted; the fake answers locally
under its honest mark; a lost key is the named 503 face and a provider that
dies before its first token the named 502 face; the second immediate call
is refused with the 429 and the wait. The audit lands under the key's task
— every provider call's row — while no domain table ever carries the draft
or the answer.
"""

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.capabilities.prompts import service as prompts_service
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter, Chunk, Document, Entity, Novel, Scene
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.embeddings import FakeEmbeddingProvider
from app.kernel.llm.repositories import AssignmentRepository, ProfileRepository, ProviderRepository
from app.kernel.llm.resolution import ResolvedProvider
from app.kernel.prompts import get_registry, no_includes, render_source
from app.kernel.prompts.models import PromptTemplateRepository
from app.kernel.secrets import KeyUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.kernel.llm.contract import CompletionEvent, CompletionRequest, TextProvider

pytestmark = pytest.mark.timeout(60)

CONTINUATION = "writing.continuation"
CHAT = "chat.ask"
EXTRACT = "knowledge.extract-entities"
CONSISTENCY = "knowledge.check-consistency"
INTERVIEW = "knowledge.entity-interview"

SAMPLE_TAIL = "Der Nebel kam von See."
# The writing sample factory's tail — what a SAMPLE-scope render would carry.
# The live test's assertions lean on its absence: the real assembly rides the
# seeded manuscript, never the samples.
PASSAGE = "Der Leuchtturm am Horizont war seit Jahren dunkel."


@pytest.fixture(autouse=True)
def _clear_live_test_ledger() -> None:
    """The rate limit is process memory: every test starts with an empty ledger."""
    prompts_service._LIVE_TEST_LAST.clear()  # pyright: ignore[reportPrivateUsage]


def _client() -> AsyncClient:
    """An HTTP client that drives the real application through ASGI."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _novel(title: str = "Die Reisende", *, updated: bool = False) -> UUID:
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title=title)
        session.add(novel)
        await session.commit()
        return novel.id


async def _chapter(novel_id: UUID, title: str = "Hafen", position: int = 0) -> UUID:
    async with Session() as session:
        chapter = Chapter(user_id=LOCAL_USER_ID, novel_id=novel_id, title=title, position=position)
        session.add(chapter)
        await session.commit()
        return chapter.id


async def _scene(chapter_id: UUID, body: str, position: int = 0, title: str = "") -> UUID:
    async with Session() as session:
        scene = Scene(
            user_id=LOCAL_USER_ID, chapter_id=chapter_id, body=body, position=position, title=title
        )
        session.add(scene)
        await session.commit()
        return scene.id


async def _entity(novel_id: UUID, name: str, type_: str) -> None:
    async with Session() as session:
        session.add(
            Entity(user_id=LOCAL_USER_ID, novel_id=novel_id, name=name, type=type_, content="")
        )
        await session.commit()


async def _passage(title: str, passage: str) -> None:
    """One document and chunk in the user's knowledge base, chat's own seed."""
    [vector] = await FakeEmbeddingProvider().embed([passage])
    async with Session() as session:
        document = Document(user_id=LOCAL_USER_ID, title=title, embedding_width=len(vector))
        session.add(document)
        await session.flush()
        session.add(
            Chunk(
                user_id=LOCAL_USER_ID,
                document_id=document.id,
                position=0,
                text=passage,
                embedding=vector,
            )
        )
        await session.commit()


async def _audit_rows() -> list[dict[str, Any]]:
    """Every audit row, as a dict — task_key, prompt_key, novel, status, texts."""
    async with Session() as session:
        found = (
            await session.execute(
                text(
                    "SELECT task_key, prompt_key, novel_id, status, prompt_text,"
                    " response_text, profile_id, model FROM llm_calls"
                )
            )
        ).all()
    keys = (
        "task_key",
        "prompt_key",
        "novel_id",
        "status",
        "prompt_text",
        "response_text",
        "profile_id",
        "model",
    )
    return [dict(zip(keys, row, strict=True)) for row in found]


def _frames(body: str) -> list[dict[str, Any]]:
    """Decode the JSON payloads of SSE data lines in their original order."""
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def _resolved(provider: TextProvider) -> ResolvedProvider:
    """A fake-tier resolved carrier for a stand-in provider the tests inject."""
    return ResolvedProvider(
        provider=provider,
        profile_id=None,
        kind="fake",
        model="fake",
        context_window=None,
        max_output_tokens=None,
        temperature=None,
        request_timeout=None,
        base_url=None,
        api_key=None,
    )


# --- the preview ------------------------------------------------------------


async def test_the_preview_renders_the_saved_effective_and_never_calls_the_model() -> None:
    """Absent body: the saved effective renders at sample scope; no row, no call."""
    async with _client() as client:
        saved = await client.put(f"/api/prompts/{CONTINUATION}", json={"content": "P: {{ tail }}"})
        assert saved.status_code == 200, saved.text

        preview = await client.post(f"/api/prompts/{CONTINUATION}/preview")
        assert preview.status_code == 200, preview.text
        body = preview.json()

    assert body["rendered"] == "P: Der Nebel kam von See."
    assert body["diagnostics"]["chars"] == len(body["rendered"])
    # The key carries no contract; the diagnostic states None, never a guess.
    assert body["diagnostics"]["contract_ok"] is None
    provenance = {variable["name"]: variable for variable in body["variables"]}
    assert provenance["tail"]["used"] is True
    assert provenance["tail"]["value"] == SAMPLE_TAIL
    assert provenance["novel_title"]["used"] is False

    # No model call, nothing persisted beyond the override the PUT wrote.
    assert await _audit_rows() == []
    async with Session() as session:
        stored = (
            (await session.execute(text("SELECT content FROM prompt_templates"))).scalars().all()
        )
    assert stored == ["P: {{ tail }}"]


async def test_the_preview_prefers_the_body_draft_over_the_saved() -> None:
    """A carried draft renders; the saved override stays the save's business."""
    async with _client() as client:
        await client.put(f"/api/prompts/{CONTINUATION}", json={"content": "SAVED {{ tail }}"})
        preview = await client.post(
            f"/api/prompts/{CONTINUATION}/preview", json={"content": "DRAFT {{ tail }}"}
        )
        assert preview.status_code == 200, preview.text

    assert preview.json()["rendered"] == "DRAFT Der Nebel kam von See."


async def test_the_preview_of_an_untouched_key_renders_the_bundled_template() -> None:
    """No override, no body: the bundled template at its sample factory."""
    spec = get_registry().spec(CONTINUATION)
    golden = render_source(spec.template, spec.sample_variables(), include=no_includes)
    async with _client() as client:
        preview = await client.post(f"/api/prompts/{CONTINUATION}/preview")
        assert preview.status_code == 200, preview.text

    assert preview.json()["rendered"] == golden


async def test_a_broken_draft_is_refused_by_the_render_s_own_reason() -> None:
    """The preview cannot render what the save would refuse: the 422 names it."""
    async with _client() as client:
        preview = await client.post(
            f"/api/prompts/{CONTINUATION}/preview", json={"content": "Hello {{ nope }}"}
        )
        assert preview.status_code == 422
        body = preview.json()["detail"]
        assert body["reason"] == "undefined-variable"
        assert "nope" in body["detail"]


async def test_a_contract_failure_is_a_diagnostic_not_a_refusal() -> None:
    """A draft that renders but drops the chat sources previews, marked unclean."""
    async with _client() as client:
        preview = await client.post(
            f"/api/prompts/{CHAT}/preview", json={"content": "Q {{ question }}"}
        )
        assert preview.status_code == 200, preview.text

    assert preview.json()["diagnostics"]["contract_ok"] is False


async def test_the_provenance_names_exactly_the_variables_the_source_reads() -> None:
    """The AST's load contexts decide `used`; the sample value rides beside it."""
    async with _client() as client:
        preview = await client.post(
            f"/api/prompts/{CONTINUATION}/preview", json={"content": "No variables at all."}
        )
        assert preview.status_code == 200, preview.text
        empty = {variable["name"]: variable["used"] for variable in preview.json()["variables"]}
        assert set(empty) >= {"novel_title", "tail"}
        assert not any(empty.values())

        named = await client.post(
            f"/api/prompts/{CONTINUATION}/preview",
            json={"content": "{{ novel_title }} {{ tail }}"},
        )
        assert named.status_code == 200, named.text
        used = {variable["name"]: variable["used"] for variable in named.json()["variables"]}
        assert used["novel_title"] is True
        assert used["tail"] is True
        assert used["chapter_title"] is False


async def test_the_preview_404s_on_an_unknown_key_and_validates_the_novel() -> None:
    """The closed key set and the owned-novel read hold on the preview too."""
    await seed_user(UUID("00000000-0000-0000-0000-000000000002"))
    async with Session() as session:
        foreign = Novel(user_id=UUID("00000000-0000-0000-0000-000000000002"), title="Fremd")
        session.add(foreign)
        await session.commit()
        foreign_id = foreign.id

    async with _client() as client:
        unknown = await client.post("/api/prompts/nope.nope/preview")
        assert unknown.status_code == 404

        preview = await client.post(
            f"/api/prompts/{CONTINUATION}/preview", params={"novel_id": str(foreign_id)}
        )
        assert preview.status_code == 422
        assert preview.json()["detail"]["reason"] == "unknown-novel"


# --- the live test: the happy wire -----------------------------------------


async def test_the_live_test_streams_the_fakes_answer_with_its_honest_mark() -> None:
    """Context frame first (the fake named), deltas, done; the audit under the task."""
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")

    async with _client() as client:
        response = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert response.status_code == 200, response.text

    frames = _frames(response.text)
    context = frames[0]["context"]
    assert context["key"] == CONTINUATION
    assert context["source"] == "effective"  # no body: the chain's pick (the bundled here)
    assert context["provider"] == "fake"
    assert context["novel_id"] is None
    assert context["facts"]["chapter"] == "Hafen"
    assert "delta" in frames[1]
    assert response.text.endswith("event: done\ndata: {}\n\n")

    rows = await _audit_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["task_key"] == CONTINUATION
    assert row["prompt_key"] == CONTINUATION
    assert row["status"] == "ok"
    assert row["novel_id"] is None


async def test_the_live_test_assembles_the_real_manuscript_not_the_samples() -> None:
    """The audit's prompt carries the seeded prose; the sample tail is nowhere."""
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id, "Hafen")
    await _scene(chapter_id, "Der Leuchtturm ward nie gebaut.")

    async with _client() as client:
        response = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert response.status_code == 200, response.text

    [row] = await _audit_rows()
    assert "Der Leuchtturm ward nie gebaut." in row["prompt_text"]
    assert SAMPLE_TAIL not in row["prompt_text"]
    assert "Novel: Die Reisende" in row["prompt_text"]
    assert "Chapter: Hafen" in row["prompt_text"]


async def test_the_editor_draft_rides_the_wire_and_is_never_persisted() -> None:
    """A draft passes the gate, serves the call, and lands in no table."""
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")
    draft = "DRAFT: {{ tail }}"

    async with _client() as client:
        saved = await client.put(
            f"/api/prompts/{CONTINUATION}", json={"content": "SAVED: {{ tail }}"}
        )
        assert saved.status_code == 200, saved.text
        response = await client.post(
            f"/api/prompts/{CONTINUATION}/live-test", json={"content": draft}
        )
        assert response.status_code == 200, response.text

    [row] = await _audit_rows()
    assert row["prompt_text"].startswith("DRAFT: ")
    assert "Der Hafen lag im Dunkel." in row["prompt_text"]

    async with Session() as session:
        overrides = (
            (await session.execute(text("SELECT content FROM prompt_templates"))).scalars().all()
        )
        scene_bodies = (await session.execute(text("SELECT body FROM scenes"))).scalars().all()
    # The draft never became an override; the manuscript is untouched.
    assert overrides == ["SAVED: {{ tail }}"]
    assert scene_bodies == ["Der Hafen lag im Dunkel."]


async def test_the_absent_body_serves_the_saved_effective() -> None:
    """No body: the override in force is the source the provider answers."""
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")

    async with _client() as client:
        saved = await client.put(
            f"/api/prompts/{CONTINUATION}", json={"content": "SAVED: {{ tail }}"}
        )
        assert saved.status_code == 200, saved.text
        response = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert response.status_code == 200, response.text

    [row] = await _audit_rows()
    assert row["prompt_text"].startswith("SAVED: ")


async def test_the_chat_live_test_retrieves_real_passages() -> None:
    """The chat assembly's sources come from the user's corpus, the question named."""
    await _passage("Notizen", PASSAGE)

    async with _client() as client:
        response = await client.post(f"/api/prompts/{CHAT}/live-test")
        assert response.status_code == 200, response.text

    frames = _frames(response.text)
    assert frames[0]["context"]["facts"]["passages"] == "1"

    [row] = await _audit_rows()
    assert row["task_key"] == CHAT
    assert PASSAGE in row["prompt_text"]
    assert "Wo war der Leuchtturm?" in row["prompt_text"]


async def test_interview_live_test_resolves_and_audits_chat_ask() -> None:
    """The fifth key rides chat.ask but audits under its own prompt key.

    The resolution follows ``spec.task_key``; the audit names the task the
    call rode and the prompt that produced it — ``chat.ask`` and
    ``knowledge.entity-interview`` — and the facts name the sample type, its
    two turns and the novel's real roster.
    """
    novel_id = await _novel("Die Reisende")
    await _entity(novel_id, "Mira", "character")

    async with _client() as client:
        response = await client.post(
            f"/api/prompts/{INTERVIEW}/live-test", json={"novel_id": str(novel_id)}
        )
        assert response.status_code == 200, response.text

    frames = _frames(response.text)
    facts = frames[0]["context"]["facts"]
    assert facts["type"] == "character"
    assert facts["turns"] == "2"
    assert facts["roster"] == "1"

    [row] = await _audit_rows()
    assert row["task_key"] == CHAT
    assert row["prompt_key"] == INTERVIEW
    assert "PURPOSE: entity-interview" in row["prompt_text"]
    assert "Mira (character; none)" in row["prompt_text"]
    assert 'novel "Die Reisende"' in row["prompt_text"]
    assert '"reply"' in row["response_text"]


async def test_the_knowledge_live_tests_assemble_the_latest_chapters() -> None:
    """Extraction rides the latest chapter's prose; consistency rides the book."""
    novel_id = await _novel("Die Reisende")
    first = await _chapter(novel_id, "Hafen", position=0)
    second = await _chapter(novel_id, "Sturm", position=1)
    await _scene(first, "Mira betrat den Hafen.", position=0)
    await _scene(second, "Der Sturm nahm das Schiff.", position=0)
    await _entity(novel_id, "Mira", "character")

    async with _client() as client:
        extract = await client.post(f"/api/prompts/{EXTRACT}/live-test")
        assert extract.status_code == 200, extract.text
        # The window is per user, not per key: clear it so the second
        # assembly runs (this test pins the assemblies, not the limit).
        prompts_service._LIVE_TEST_LAST.clear()  # pyright: ignore[reportPrivateUsage]
        check = await client.post(f"/api/prompts/{CONSISTENCY}/live-test")
        assert check.status_code == 200, check.text

    rows = {row["task_key"]: row for row in await _audit_rows()}
    assert "PURPOSE: extract-entities" in rows[EXTRACT]["prompt_text"]
    assert "Chapter: Sturm" in rows[EXTRACT]["prompt_text"]
    assert "Der Sturm nahm das Schiff." in rows[EXTRACT]["prompt_text"]

    assert "PURPOSE: check-consistency" in rows[CONSISTENCY]["prompt_text"]
    assert "Chapter: Hafen" in rows[CONSISTENCY]["prompt_text"]
    assert "Chapter: Sturm" in rows[CONSISTENCY]["prompt_text"]
    assert "Mira (character)" in rows[CONSISTENCY]["prompt_text"]


async def test_the_extraction_assembly_never_names_a_foreign_novel() -> None:
    """The chapter's parent novel is read through the owner predicate.

    The inconsistent row (our chapter pointing at another user's novel) can
    only arrive around the API, which owns the checks — the assembly's own
    read must still answer nothing rather than name a book that is not ours.
    """
    other = UUID("00000000-0000-0000-0000-000000000002")
    await seed_user(other)
    async with Session() as session:
        foreign = Novel(user_id=other, title="Fremdes Buch")
        session.add(foreign)
        await session.flush()
        chapter = Chapter(user_id=LOCAL_USER_ID, novel_id=foreign.id, title="Kapitel", position=0)
        session.add(chapter)
        await session.commit()
        chapter_id = chapter.id
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")

    async with _client() as client:
        response = await client.post(f"/api/prompts/{EXTRACT}/live-test")
        assert response.status_code == 200, response.text

    facts = _frames(response.text)[0]["context"]["facts"]
    assert "novel" not in facts
    [row] = await _audit_rows()
    assert "Fremdes Buch" not in row["prompt_text"]


async def test_the_call_rides_the_key_s_task_assignment() -> None:
    """The cascade serves the call; the audit names the assigned profile."""
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")

    async with Session() as session:
        providers = ProviderRepository(session, LOCAL_USER_ID)
        provider = await providers.create(name="Lokal", kind="fake", base_url="")
        profile = await ProfileRepository(session, LOCAL_USER_ID).create(
            name="Fake-Turbo", provider_id=provider.id, model="fake-turbo"
        )
        await AssignmentRepository(session, LOCAL_USER_ID).set(
            CONTINUATION, profile.id, "balanced", None
        )
        await session.commit()
        profile_id = profile.id

    async with _client() as client:
        response = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert response.status_code == 200, response.text

    [row] = await _audit_rows()
    assert row["profile_id"] == profile_id
    assert row["model"] == "fake-turbo"


async def test_the_live_budget_is_the_task_s_reservation_not_the_model_ceiling() -> None:
    """The live call assembles under the same reserve as continuation.

    The model's stored ceiling fills the window on purpose: budgeting with
    the ceiling would refuse the pair, while the ``quick`` profile reserves
    1 024 inside it. The live test must assemble what continuation
    assembles — same prompt, byte for byte — not a narrower context.
    """
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    scene_id = await _scene(chapter_id, "Der Hafen lag im Dunkel.")

    async with Session() as session:
        providers = ProviderRepository(session, LOCAL_USER_ID)
        provider = await providers.create(name="Lokal", kind="fake", base_url="")
        profile = await ProfileRepository(session, LOCAL_USER_ID).create(
            name="Fake-Quick",
            provider_id=provider.id,
            model="fake-quick",
            context_window=1500,
            max_output_tokens=2000,
        )
        await AssignmentRepository(session, LOCAL_USER_ID).set(
            CONTINUATION, profile.id, "quick", None
        )
        await session.commit()

    async with _client() as client:
        continuation = await client.post(f"/api/writing/scenes/{scene_id}/continue")
        assert continuation.status_code == 200, continuation.text
        live = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert live.status_code == 200, live.text

    # Both calls audited under the key: the prompts they carried are one
    # prompt. The ceiling budget would have refused the live call (422).
    texts = {row["prompt_text"] for row in await _audit_rows()}
    assert len(texts) == 1
    [prompt] = texts
    assert "Der Hafen lag im Dunkel." in prompt


async def test_a_draftless_global_writing_test_rides_the_global_chain() -> None:
    """No global override, no draft: the test executes the global template the
    editor shows. The latest scene's novel override must not stand in for it.

    With the source left unset at the requested (global) scope, the assembly
    resolved the chain at the scene's novel and executed that override while
    the context frame reported ``novel_id: null``.
    """
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")
    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(
            CONTINUATION, "NOVEL-OVERRIDE: {{ tail }}", novel_id
        )
        await session.commit()

    async with _client() as client:
        response = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert response.status_code == 200, response.text

    assert _frames(response.text)[0]["context"]["source"] == "effective"
    [row] = await _audit_rows()
    assert "NOVEL-OVERRIDE" not in row["prompt_text"]
    assert row["prompt_text"].startswith("Novel: ")  # the bundled arrangement


async def test_a_test_s_includes_resolve_at_the_request_s_scope() -> None:
    """The include chain follows the requested tier: global test → global rows.

    Both include sources live at the same two tiers, so the text names which
    one the render walked. The novel test pins the other direction — the
    scope parameter must not flatten every test to global.
    """
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")
    async with Session() as session:
        templates = PromptTemplateRepository(session, LOCAL_USER_ID)
        await templates.save(CONTINUATION, "TOP {% include 'knowledge.extract-entities' %}", None)
        await templates.save(EXTRACT, "GLOBAL-INCLUDE {{ tail }}", None)
        await templates.save(EXTRACT, "NOVEL-INCLUDE {{ tail }}", novel_id)
        await session.commit()

    async with _client() as client:
        global_run = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert global_run.status_code == 200, global_run.text
        prompts_service._LIVE_TEST_LAST.clear()  # pyright: ignore[reportPrivateUsage]
        novel_run = await client.post(
            f"/api/prompts/{CONTINUATION}/live-test", json={"novel_id": str(novel_id)}
        )
        assert novel_run.status_code == 200, novel_run.text

    rows = {row["novel_id"]: row for row in await _audit_rows()}
    assert "GLOBAL-INCLUDE" in rows[None]["prompt_text"]
    assert "NOVEL-INCLUDE" not in rows[None]["prompt_text"]
    assert "NOVEL-INCLUDE" in rows[novel_id]["prompt_text"]


# --- the live test: the gated paths ----------------------------------------


async def test_a_draft_that_fails_the_gate_is_refused_before_any_call() -> None:
    """The sandbox runs first: 422, no provider call, and the window not burned."""
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")

    async with _client() as client:
        refused = await client.post(
            f"/api/prompts/{CONTINUATION}/live-test", json={"content": "Hello {{ nope }}"}
        )
        assert refused.status_code == 422
        assert refused.json()["detail"]["reason"] == "undefined-variable"
        assert await _audit_rows() == []

        # The refused draft consumed no rate-limit window: the next call goes through.
        allowed = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert allowed.status_code == 200, allowed.text


async def test_a_real_scope_budget_refusal_is_a_named_422() -> None:
    """A frame the immediate slice cannot hold refuses `budget`, as production would."""
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")
    # The fake's default budgets leave ~15k characters of immediate text; a
    # fixed frame wider than that cannot hold even an empty tail.
    draft = "X" * 16_000 + "{{ tail }}"

    async with _client() as client:
        refused = await client.post(
            f"/api/prompts/{CONTINUATION}/live-test", json={"content": draft}
        )
        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"]["reason"] == "budget"
        assert await _audit_rows() == []


async def test_a_lost_key_is_the_named_503_face_before_any_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The secret store's refusal is the 503; no audit row claims a call."""
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")

    async def lost_key(session: AsyncSession, user_id: UUID, task_key: str) -> ResolvedProvider:
        raise KeyUnavailableError("the key of provider 00000000-0000-0000-0000-000000000009")

    monkeypatch.setattr(prompts_service, "resolve_provider", lost_key)
    async with _client() as client:
        response = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert response.status_code == 503
        body = response.json()["detail"]
        assert body["code"] == "key-unavailable"
        assert "00000000-0000-0000-0000-000000000009" in body["detail"]
        assert await _audit_rows() == []


class _DyingProvider:
    """Answers nothing and dies before its first token: the pre-stream 502."""

    def __init__(self, failure: Exception) -> None:
        self.failure = failure

    def describe(self) -> str:
        return "dying"

    def configuration_problems(self) -> list[str]:
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        raise self.failure
        yield  # pragma: no cover — the raise above makes this an async generator


async def test_a_provider_that_dies_before_its_first_token_is_the_502_face(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The upstream failed before the stream could start: 502, and the audit row."""
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")

    async def dying(session: AsyncSession, user_id: UUID, task_key: str) -> ResolvedProvider:
        return _resolved(_DyingProvider(RuntimeError("the provider died")))

    monkeypatch.setattr(prompts_service, "resolve_provider", dying)
    async with _client() as client:
        response = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert response.status_code == 502, response.text
        body = response.json()["detail"]
        assert body["code"] == "unknown"
        assert body["detail"] == "the provider died"

    # The call ran — its attempt is what failed — so the audit carries the row.
    [row] = await _audit_rows()
    assert row["status"] == "error"


async def test_no_manuscript_context_is_a_named_409() -> None:
    """Real assembly, not samples: with nothing written, the face names the gap."""
    async with _client() as client:
        response = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert response.status_code == 409, response.text
        body = response.json()["detail"]
        assert body["code"] == "no-context"
        assert await _audit_rows() == []

        # The refused call consumed no rate-limit window either.
        seed = await _novel()
        chapter = await _chapter(seed)
        await _scene(chapter, "Der Hafen lag im Dunkel.")
        allowed = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert allowed.status_code == 200, allowed.text


async def test_the_second_immediate_call_is_refused_with_the_wait() -> None:
    """One live test per window: the next is the 429 with Retry-After."""
    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")

    async with _client() as client:
        first = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert first.status_code == 200, first.text

        second = await client.post(f"/api/prompts/{CONTINUATION}/live-test")
        assert second.status_code == 429, second.text
        assert second.json()["detail"]["code"] == "rate-limited"
        retry_after = second.headers["Retry-After"]
        assert (
            retry_after.isdigit()
            and 0 < int(retry_after) <= prompts_service.LIVE_TEST_COOLDOWN_SECONDS
        )


async def test_a_rate_limited_request_never_reaches_the_embed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The window is peeked before the assembly: the refusal precedes the cost.

    Chat's assembly is the witness — its retrieval embeds the query before
    anything else runs. The first test claims the window; the second is
    refused with zero embedding calls, the peek having fired before the
    assembly could start.
    """
    await _passage("Notizen", PASSAGE)

    async with _client() as client:
        first = await client.post(f"/api/prompts/{CHAT}/live-test")
        assert first.status_code == 200, first.text

    calls = 0
    original = FakeEmbeddingProvider.embed

    async def counting(self: FakeEmbeddingProvider, texts: list[str]) -> list[list[float]]:
        nonlocal calls
        calls += 1
        return await original(self, texts)

    monkeypatch.setattr(FakeEmbeddingProvider, "embed", counting)
    async with _client() as client:
        second = await client.post(f"/api/prompts/{CHAT}/live-test")
        assert second.status_code == 429, second.text
        assert second.json()["detail"]["code"] == "rate-limited"
    assert calls == 0


async def test_the_live_test_404s_and_holds_the_scope_rules() -> None:
    """The closed key set, the novel-scope rule and the owned-novel read."""
    await seed_user(UUID("00000000-0000-0000-0000-000000000002"))
    async with Session() as session:
        foreign = Novel(user_id=UUID("00000000-0000-0000-0000-000000000002"), title="Fremd")
        session.add(foreign)
        await session.commit()
        foreign_id = foreign.id

    novel_id = await _novel()
    chapter_id = await _chapter(novel_id)
    await _scene(chapter_id, "Der Hafen lag im Dunkel.")

    async with _client() as client:
        unknown = await client.post("/api/prompts/nope.nope/live-test")
        assert unknown.status_code == 404

        scoped = await client.post(
            f"/api/prompts/{CHAT}/live-test", json={"novel_id": str(novel_id)}
        )
        assert scoped.status_code == 422
        assert scoped.json()["detail"]["reason"] == "novel-scope"

        foreign_test = await client.post(
            f"/api/prompts/{CONTINUATION}/live-test", json={"novel_id": str(foreign_id)}
        )
        assert foreign_test.status_code == 422
        assert foreign_test.json()["detail"]["reason"] == "unknown-novel"
