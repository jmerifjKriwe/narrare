"""The interview's five endpoints and one turn's three steps.

A stub provider sits at the boundary (the one fake the rules allow) and scripts
the model; the real service, repositories and database run below it. Two users
prove the scope, and the racing test proves the merge under the session's lock.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.capabilities.chat import interviews
from app.capabilities.chat.prompts import ROSTER_CUT_LINE
from app.capabilities.chat.repository import AssistantSessionRepository
from app.capabilities.chat.schemas import TurnCreate
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Entity, Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.contract import (
    DONE,
    USER_PREFIX,
    CompletionEvent,
    CompletionRequest,
    Delta,
    TextProvider,
    Usage,
)
from app.kernel.llm.resolution import ResolvedProvider
from app.kernel.prompts.models import PromptTemplateRepository
from app.kernel.secrets import KeyUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.capabilities.chat.models import AssistantTurn
    from app.capabilities.chat.schemas import TurnAct

pytestmark = pytest.mark.timeout(60)

MODE = "knowledge.entity"
OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
async def two_users(empty_tables: None, schema: None) -> None:
    """The local writer and one stranger: ownership is what the scope reads."""
    await seed_user(OTHER_USER)


def _client() -> AsyncClient:
    """An HTTP client that drives the real application through ASGI."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _resolving(
    provider: TextProvider,
) -> Callable[[AsyncSession, UUID, str], Awaitable[ResolvedProvider]]:
    """A resolve_provider stand-in that always serves the scripted provider."""

    async def resolve(session: AsyncSession, user_id: UUID, task_key: str) -> ResolvedProvider:
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

    return resolve


class _StubProvider:
    """A TextProvider at the boundary: scripted answers, or the slots echoed back."""

    def __init__(self, answers: list[str] | None = None, *, echo: bool = False) -> None:
        self.answers = answers
        self.echo = echo
        self.requests: list[CompletionRequest] = []

    def describe(self) -> str:
        """Identify the scripted stand-in."""
        return "stub"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Answer with the next scripted line, or with the prompt's own slots."""
        self.requests.append(request)
        prompt = "\n".join(
            message.content for message in request.messages if message.role == "user"
        )
        if self.echo:
            slots = _prompt_json(prompt, "SLOTS: ", {})
            relations = _prompt_json(prompt, "RELATIONS: ", [])
            answer = json.dumps(
                {"reply": "Notiert.", "slots": slots, "relations": relations},
                ensure_ascii=False,
            )
        else:
            assert self.answers, "the stub ran out of scripted answers"
            answer = self.answers.pop(0)
        yield Delta(answer)
        yield Usage(input_tokens=1, output_tokens=1)
        yield DONE


class _FailingProvider:
    """A provider that dies on the scripted failure: the provider-error path."""

    def __init__(self, failure: Exception, *, delay: float = 0.0) -> None:
        self.failure = failure
        self.delay = delay
        self.requests: list[CompletionRequest] = []

    def describe(self) -> str:
        """Identify the provider that refuses to answer."""
        return "failing"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Wait out the scripted delay, then raise before a single event."""
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        raise self.failure
        yield Delta("")  # pragma: no cover — the raise above makes this unreachable


class _RacingProvider:
    """Two calls, held until each has read the same starting proposal.

    The first call parks on an event until the second has arrived; the second
    releases both. Turn A adds an alias, turn B a tag, both echoing the slots
    their own prompt carried — the same starting proposal.
    """

    def __init__(self) -> None:
        self.calls = 0
        self.first_arrived = asyncio.Event()
        self.second_arrived = asyncio.Event()

    def describe(self) -> str:
        """Identify the barrier provider."""
        return "racing"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Hold until both calls have read, then answer each with its own change."""
        self.calls += 1
        call = self.calls
        prompt = "\n".join(
            message.content for message in request.messages if message.role == "user"
        )
        raw_slots = _prompt_json(prompt, "SLOTS: ", {})
        slots = dict(cast("dict[str, object]", raw_slots)) if isinstance(raw_slots, dict) else {}
        relations = _prompt_json(prompt, "RELATIONS: ", [])
        if call == 1:
            self.first_arrived.set()
            await self.second_arrived.wait()
            aliases = cast("list[object]", slots.get("aliases", []))
            slots["aliases"] = [*aliases, "Die Wächterin"]
        else:
            await self.first_arrived.wait()
            self.second_arrived.set()
            tags = cast("list[object]", slots.get("tags", []))
            slots["tags"] = [*tags, "wachsam"]
        yield Delta(
            json.dumps(
                {"reply": "Notiert.", "slots": slots, "relations": relations},
                ensure_ascii=False,
            )
        )
        yield Usage(input_tokens=1, output_tokens=1)
        yield DONE


class _AliasRacingProvider:
    """Two calls, both adding an alias to one list slot from the same start.

    The first call parks until the second has read the same starting proposal;
    the second releases both. Each answers with its own alias appended to the
    slots its prompt carried, so the merge must union the two additions.
    """

    def __init__(self) -> None:
        self.calls = 0
        self.first_arrived = asyncio.Event()
        self.second_arrived = asyncio.Event()

    def describe(self) -> str:
        """Identify the barrier provider."""
        return "alias-racing"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Hold until both calls have read, then answer each with its own alias."""
        self.calls += 1
        call = self.calls
        prompt = "\n".join(
            message.content for message in request.messages if message.role == "user"
        )
        raw_slots = _prompt_json(prompt, "SLOTS: ", {})
        slots = dict(cast("dict[str, object]", raw_slots)) if isinstance(raw_slots, dict) else {}
        relations = _prompt_json(prompt, "RELATIONS: ", [])
        if call == 1:
            self.first_arrived.set()
            await self.second_arrived.wait()
            alias = "Die Wächterin"
        else:
            await self.first_arrived.wait()
            self.second_arrived.set()
            alias = "Die Hüterin"
        aliases = cast("list[object]", slots.get("aliases", []))
        slots["aliases"] = [*aliases, alias]
        yield Delta(
            json.dumps(
                {"reply": "Notiert.", "slots": slots, "relations": relations},
                ensure_ascii=False,
            )
        )
        yield Usage(input_tokens=1, output_tokens=1)
        yield DONE


class _ClosingProvider:
    """Answers once, but closes the interview from a second session first.

    The close lands while the first call is in flight, after step 1 read the
    session as open and before step 3 takes the lock: the «closed while the
    model answered» race, driven through its real window.
    """

    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        self.requests: list[CompletionRequest] = []

    def describe(self) -> str:
        """Identify the closing stand-in."""
        return "closing"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Close the session from another session, then answer."""
        self.requests.append(request)
        async with Session() as session:
            repo = AssistantSessionRepository(session, LOCAL_USER_ID)
            row = await repo.get(self.session_id)
            assert row is not None
            if row.closed_at is None:
                await repo.close(row)
                await session.commit()
        yield Delta(
            json.dumps({"reply": "Notiert.", "slots": {}, "relations": []}, ensure_ascii=False)
        )
        yield Usage(input_tokens=1, output_tokens=1)
        yield DONE


class _NewSuggestionProvider:
    """Answers once, but stores a newer pending suggestion from a second session first.

    The new suggestion lands while the accepted turn's model call is in
    flight, after step 1 captured the pending one and before step 3 takes the
    lock: the window in which the turn must refuse rather than accept the
    newer suggestion under an answer generated for the older one.
    """

    def __init__(self, session_id: UUID, suggestion: str) -> None:
        self.session_id = session_id
        self.suggestion = suggestion
        self.requests: list[CompletionRequest] = []

    def describe(self) -> str:
        """Identify the racing stand-in."""
        return "new-suggestion"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Store a newer pending suggestion from another session, then answer."""
        self.requests.append(request)
        async with Session() as session:
            repo = AssistantSessionRepository(session, LOCAL_USER_ID)
            seq = await repo.next_seq(self.session_id)
            await repo.append_turn(
                self.session_id,
                seq,
                "assistant",
                "Noch eine Frage?",
                suggestion=self.suggestion,
                suggestion_state="pending",
            )
            await session.commit()
        yield Delta(
            json.dumps(
                {"reply": "Notiert.", "slots": {"name": "Jona"}, "relations": []},
                ensure_ascii=False,
            )
        )
        yield Usage(input_tokens=1, output_tokens=1)
        yield DONE


class _ConcurrentSaveProvider:
    """Answers once, but saves a proposal from a second session first.

    The save lands while the turn's model call is in flight, after step 1 read
    the proposal and before step 3 takes the lock: the window in which an
    answer echoing the empty input it was given must not erase what the other
    turn saved, while an answer that changes a value it was given still does.
    """

    def __init__(
        self,
        session_id: UUID,
        proposal: dict[str, object],
        slots: dict[str, object],
    ) -> None:
        self.session_id = session_id
        self.proposal = proposal
        self.slots = slots
        self.requests: list[CompletionRequest] = []

    def describe(self) -> str:
        """Identify the racing stand-in."""
        return "concurrent-save"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Save the other turn's proposal, then answer with the given slots."""
        self.requests.append(request)
        async with Session() as session:
            repo = AssistantSessionRepository(session, LOCAL_USER_ID)
            row = await repo.get(self.session_id)
            assert row is not None
            await repo.set_proposal(row, self.proposal)
            await session.commit()
        yield Delta(
            json.dumps(
                {"reply": "Notiert.", "slots": self.slots},
                ensure_ascii=False,
            )
        )
        yield Usage(input_tokens=1, output_tokens=1)
        yield DONE


class _ConcurrentTurnProvider:
    """Answers A once, but takes turn B from a second session first.

    The first call — A, the outer turn — runs B through the real service while
    A's model call is in flight. A plain B re-enters this stand-in and is
    answered by ``b_answer``; a B act the model does not serve
    (``drop-suggestions``) runs on the stored session alone. A then answers
    ``a_answer``, echoing the input its call was given.
    """

    def __init__(
        self,
        session_id: UUID,
        *,
        act: TurnAct | None,
        b_answer: str | None,
        a_answer: str,
    ) -> None:
        self.session_id = session_id
        self.act: TurnAct | None = act
        self.b_answer = b_answer
        self.a_answer = a_answer
        self.calls = 0
        self.requests: list[CompletionRequest] = []

    def describe(self) -> str:
        """Identify the racing stand-in."""
        return "concurrent-turn"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Take B's turn from another session, then answer A's call."""
        self.requests.append(request)
        self.calls += 1
        if self.calls == 1:
            async with Session() as session:
                await interviews.InterviewService(session, LOCAL_USER_ID).take_turn(
                    self.session_id,
                    TurnCreate(text="Noch etwas.", act=self.act),
                )
            yield Delta(self.a_answer)
        else:
            assert self.b_answer is not None, "B's plain turn ran without its scripted answer"
            yield Delta(self.b_answer)
        yield Usage(input_tokens=1, output_tokens=1)
        yield DONE


class _MalformedThenFailingProvider:
    """First answer is prose; the retry raises before a single event.

    The completed first attempt's row must keep its own extraction failure
    beside the retry's provider error.
    """

    def __init__(self, failure: Exception) -> None:
        self.failure = failure
        self.calls = 0

    def describe(self) -> str:
        """Identify the failing retry stand-in."""
        return "malformed-then-failing"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Answer unordered prose once, then die on the retry."""
        self.calls += 1
        if self.calls == 1:
            yield Delta("this is prose, not JSON {{")
            yield Usage(input_tokens=1, output_tokens=1)
            yield DONE
            return
        raise self.failure


def _prompt_json(prompt: str, prefix: str, default: object) -> object:
    """The JSON payload on a marked line, or the default when absent."""
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return json.loads(line.removeprefix(prefix))
    return default


def _prompt_block(prompt: str, start: str, end: str) -> list[str]:
    """The lines between a marker line and the next line that begins ``end``."""
    lines = prompt.splitlines()
    begin = lines.index(start) + 1
    finish = next(index for index in range(begin, len(lines)) if lines[index].startswith(end))
    return lines[begin:finish]


def _user_prompt(request: CompletionRequest) -> str:
    """The prompt text the provider received, joined as the kernel joins it."""
    return "\n".join(message.content for message in request.messages if message.role == "user")


async def _seed_novel(
    title: str = "The Lighthouse",
    genre: str | None = None,
    user_id: UUID = LOCAL_USER_ID,
) -> Novel:
    """A novels row straight through the session — the row's shape, not a flow."""
    async with Session() as session:
        novel = Novel(user_id=user_id, title=title, genre=genre)
        session.add(novel)
        await session.commit()
        return novel


async def _seed_session(
    novel: Novel,
    *,
    proposal: dict[str, object] | None = None,
    closed: bool = False,
    user_id: UUID = LOCAL_USER_ID,
    entity_type: str = "character",
) -> UUID:
    """An open (or closed) interview, optionally already carrying a proposal."""
    async with Session() as session:
        repo = AssistantSessionRepository(session, user_id)
        created = await repo.create(novel.id, MODE, entity_type, None)
        if proposal is not None:
            await repo.set_proposal(created, proposal)
        if closed:
            await repo.close(created)
        await session.commit()
        return created.id


async def _seed_suggestion(session_id: UUID, text_: str = "Vielleicht Mira.") -> None:
    """One pending assistant suggestion, the turn an accept or reject settles."""
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        await repo.append_turn(
            session_id,
            1,
            "assistant",
            "Wie heißt sie?",
            suggestion=text_,
            suggestion_state="pending",
        )
        await session.commit()


async def _stored_turns(session_id: UUID) -> list[AssistantTurn]:
    """Every stored turn, oldest first, as the database holds it."""
    async with Session() as session:
        return await AssistantSessionRepository(session, LOCAL_USER_ID).last_turns(session_id, 100)


async def _seed_turns(session_id: UUID, count: int) -> None:
    """Fill the transcript with ``count`` numbered user turns, oldest first."""
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        for seq in range(1, count + 1):
            await repo.append_turn(session_id, seq, "user", f"Turn {seq}")
        await session.commit()


async def _seed_entities(novel: Novel, count: int) -> None:
    """Put ``count`` roster entities in the novel, name-ordered and distinct."""
    async with Session() as session:
        session.add_all(
            Entity(
                user_id=LOCAL_USER_ID,
                novel_id=novel.id,
                name=f"Entity {index:03d}",
                type="character",
            )
            for index in range(count)
        )
        await session.commit()


async def _seed_entity_id(novel: Novel, name: str = "Mira", user_id: UUID = LOCAL_USER_ID) -> UUID:
    """One stored entity, its id returned for a door's target."""
    async with Session() as session:
        entity = Entity(user_id=user_id, novel_id=novel.id, name=name, type="character")
        session.add(entity)
        await session.commit()
        return entity.id


async def _set_created_at(session_id: UUID, moment: datetime) -> None:
    """Stamp a session's creation so list ordering is checkable, not clock-luck."""
    async with Session() as session:
        await session.execute(
            text("UPDATE assistant_sessions SET created_at = :moment WHERE id = :id"),
            {"moment": moment, "id": session_id},
        )
        await session.commit()


async def _save_override(prompt_key: str, content: str, novel_id: UUID | None) -> None:
    """Store a prompt override the way the prompts editor does, sans validation."""
    async with Session() as session:
        await PromptTemplateRepository(session, LOCAL_USER_ID).save(prompt_key, content, novel_id)
        await session.commit()


async def _audit_rows() -> list[tuple[str, str, str]]:
    """The audit's task key, prompt key and status, in insertion order."""
    async with Session() as session:
        rows = (
            await session.execute(
                text("SELECT task_key, prompt_key, status FROM llm_calls ORDER BY id")
            )
        ).all()
    return [(row.task_key, row.prompt_key, row.status) for row in rows]


async def _audit_details() -> list[dict[str, object]]:
    """The audit's successful and failed facts, in insertion order."""
    async with Session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT status, error_code, error, prompt_text, response_text, latency_ms "
                    "FROM llm_calls ORDER BY id"
                )
            )
        ).all()
    return [
        {
            "status": row.status,
            "error_code": row.error_code,
            "error": row.error,
            "prompt_text": row.prompt_text,
            "response_text": row.response_text,
            "latency_ms": row.latency_ms,
        }
        for row in rows
    ]


def _proposal(**overrides: object) -> dict[str, object]:
    """A full proposal in the shape the session stores."""
    proposal: dict[str, object] = {
        "name": None,
        "name_suggested": False,
        "aliases": [],
        "tags": [],
        "content": "",
        "suggested": {"aliases": [], "tags": [], "content": False},
        "relations": [],
    }
    proposal.update(overrides)
    return proposal


COMPLETE = _proposal(
    name="Mira",
    aliases=["Die Wächterin"],
    tags=["wachsam"],
    content="Eine Wächterin am See.",
    suggested={"aliases": [], "tags": ["wachsam"], "content": True},
    relations=[
        {"target": "Haus", "type": "located_in", "note": "", "suggested": False},
    ],
)
"""A proposal with every slot set and mixed provenance: fill-all must not move it."""


@pytest.mark.usefixtures("two_users")
async def test_open_requires_a_known_mode_and_type() -> None:
    """A mode or type outside the contract is a coded 422; a valid open lands."""
    novel = await _seed_novel()
    async with _client() as client:
        for body, code in (
            (
                {"mode": "writing.chat", "novel_id": str(novel.id), "entity_type": "character"},
                "mode-unknown",
            ),
            ({"mode": MODE, "novel_id": str(novel.id)}, "entity-type-required"),
            (
                {"mode": MODE, "novel_id": str(novel.id), "entity_type": "dragon"},
                "entity-type-unknown",
            ),
        ):
            response = await client.post("/api/chat/sessions", json=body)
            assert response.status_code == 422
            assert response.json()["detail"]["code"] == code

        opened = await client.post(
            "/api/chat/sessions",
            json={"mode": MODE, "novel_id": str(novel.id), "entity_type": "character"},
        )
    assert opened.status_code == 201
    assert opened.json()["proposal"] is None
    assert opened.json()["closed_at"] is None


@pytest.mark.usefixtures("two_users")
async def test_foreign_novel_is_404() -> None:
    """Opening an interview on another user's novel answers as absent."""
    foreign = await _seed_novel(user_id=OTHER_USER)
    async with _client() as client:
        for novel_id in (foreign.id, uuid4()):
            response = await client.post(
                "/api/chat/sessions",
                json={"mode": MODE, "novel_id": str(novel_id), "entity_type": "character"},
            )
            assert response.status_code == 404
            assert response.json()["detail"]["code"] == "not-found"


@pytest.mark.usefixtures("two_users")
async def test_open_stores_only_a_target_that_is_this_novels() -> None:
    """A target is the novel's own entity: own is stored, foreign and absent are one 404."""
    novel = await _seed_novel()
    other_novel = await _seed_novel(title="The Other Lighthouse")
    own = await _seed_entity_id(novel)
    elsewhere = await _seed_entity_id(other_novel, name="Haus")
    foreign_novel = await _seed_novel(title="Their Lighthouse", user_id=OTHER_USER)
    foreign = await _seed_entity_id(foreign_novel, user_id=OTHER_USER)

    async with _client() as client:
        opened = await client.post(
            "/api/chat/sessions",
            json={
                "mode": MODE,
                "novel_id": str(novel.id),
                "entity_type": "character",
                "target_id": str(own),
            },
        )
        refused = [
            await client.post(
                "/api/chat/sessions",
                json={
                    "mode": MODE,
                    "novel_id": str(novel.id),
                    "entity_type": "character",
                    "target_id": str(target),
                },
            )
            for target in (elsewhere, foreign, uuid4())
        ]

    assert opened.status_code == 201
    assert opened.json()["target_id"] == str(own)
    assert [response.status_code for response in refused] == [404, 404, 404]
    assert refused[0].json() == refused[1].json() == refused[2].json()
    assert all(response.json()["detail"]["code"] == "not-found" for response in refused)


@pytest.mark.usefixtures("two_users")
async def test_list_sessions_is_the_novels_own() -> None:
    """The list is this user's sessions in the novel; a stranger's row is absent."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    # The user predicate on its own: a stranger's session in *this* novel, which
    # the novel check above the list would let through.
    await _seed_session(novel, user_id=OTHER_USER)
    foreign = await _seed_novel(user_id=OTHER_USER)
    async with _client() as client:
        listed = await client.get("/api/chat/sessions", params={"novel_id": str(novel.id)})
        missing = await client.get("/api/chat/sessions", params={"novel_id": str(foreign.id)})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [str(session_id)]
    assert listed.json()["items"][0]["name"] is None
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "not-found"


@pytest.mark.usefixtures("two_users")
async def test_a_session_list_row_carries_the_proposals_name_not_the_proposal() -> None:
    """A row is the summary shape: identity, type, state and the draft's name."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel,
        proposal=_proposal(name="Mira", content="Eine Wächterin am See."),
    )
    async with _client() as client:
        listed = await client.get("/api/chat/sessions", params={"novel_id": str(novel.id)})

    assert listed.status_code == 200
    [row] = listed.json()["items"]
    assert set(row) == {
        "id",
        "novel_id",
        "mode",
        "entity_type",
        "target_id",
        "name",
        "closed_at",
        "created_at",
        "updated_at",
    }
    assert row["id"] == str(session_id)
    assert row["name"] == "Mira"
    assert "proposal" not in row


@pytest.mark.usefixtures("two_users")
async def test_a_turn_writes_two_rows_and_the_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One answer stores the writer's turn and the model's, and merges the proposal."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    provider = _StubProvider(
        [
            json.dumps(
                {
                    "reply": "Notiert. Wie sieht sie aus?",
                    "slots": {
                        "name": "Mira",
                        "aliases": ["Die Wächterin"],
                        "tags": ["wachsam"],
                        "content": "Eine Wächterin am See.",
                    },
                    "relations": [{"target": "Haus", "type": "located_in", "note": "am See"}],
                },
                ensure_ascii=False,
            )
        ]
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )
        assert response.status_code == 200
        body = response.json()
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert body["reply"] == "Notiert. Wie sieht sie aus?"
    assert body["suggestion"] is None
    assert body["seq"] == 2
    assert body["proposal"] == _proposal(
        name="Mira",
        aliases=["Die Wächterin"],
        tags=["wachsam"],
        content="Eine Wächterin am See.",
        relations=[{"target": "Haus", "type": "located_in", "note": "am See", "suggested": False}],
    )
    turns = detail.json()["turns"]
    assert [(turn["seq"], turn["role"], turn["text"]) for turn in turns] == [
        (1, "user", "Sie heißt Mira."),
        (2, "assistant", "Notiert. Wie sieht sie aus?"),
    ]
    assert await _audit_rows() == [("chat.ask", "knowledge.entity-interview", "ok")]


@pytest.mark.usefixtures("two_users")
async def test_a_written_proposal_round_trips_through_the_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The per-item shape a turn writes is the shape the detail read validates."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    provider = _StubProvider(
        [
            json.dumps(
                {
                    "reply": "Notiert.",
                    "slots": {
                        "name": "Mira",
                        "aliases": ["Die Wächterin"],
                        "tags": ["wachsam"],
                        "content": "Eine Wächterin am See.",
                    },
                    "relations": [{"target": "Haus", "type": "located_in", "note": ""}],
                },
                ensure_ascii=False,
            )
        ]
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        turn = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert turn.status_code == 200
    written = turn.json()["proposal"]
    assert detail.status_code == 200
    assert detail.json()["proposal"] == written


@pytest.mark.usefixtures("two_users")
async def test_fill_all_marks_its_parts_and_a_plain_turn_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fill-all marks every new part suggested; a plain answer marks it the writer's."""
    answer = json.dumps(
        {
            "reply": "Alles vorgeschlagen.",
            "slots": {
                "name": "Mira",
                "aliases": ["Die Wächterin"],
                "tags": ["wachsam"],
                "content": "Eine Wächterin am See.",
            },
            "relations": [{"target": "Haus", "type": "located_in"}],
        },
        ensure_ascii=False,
    )
    novel = await _seed_novel()
    filled_id = await _seed_session(novel)
    plain_id = await _seed_session(novel)

    async with _client() as client:
        monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))
        filled = await client.post(
            f"/api/chat/sessions/{filled_id}/turns",
            json={"text": "Alles vorschlagen lassen", "act": "fill-all"},
        )
        monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))
        plain = await client.post(
            f"/api/chat/sessions/{plain_id}/turns", json={"text": "Sie heißt Mira."}
        )

    assert filled.status_code == 200
    assert filled.json()["proposal"] == _proposal(
        name="Mira",
        name_suggested=True,
        aliases=["Die Wächterin"],
        tags=["wachsam"],
        content="Eine Wächterin am See.",
        suggested={"aliases": ["Die Wächterin"], "tags": ["wachsam"], "content": True},
        relations=[{"target": "Haus", "type": "located_in", "note": "", "suggested": True}],
    )
    assert plain.status_code == 200
    assert plain.json()["proposal"] == _proposal(
        name="Mira",
        aliases=["Die Wächterin"],
        tags=["wachsam"],
        content="Eine Wächterin am See.",
        relations=[{"target": "Haus", "type": "located_in", "note": "", "suggested": False}],
    )


@pytest.mark.usefixtures("two_users")
async def test_no_idea_sets_a_pending_suggestion_and_keeps_the_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """no-idea proposes an answer, keeps the proposal, and leaves a pending turn.

    The stub returns a changed slot beside its suggestion; the guess must not
    land in the proposal as the writer's own.
    """
    novel = await _seed_novel()
    proposal = _proposal(name="Mira")
    session_id = await _seed_session(novel, proposal=proposal)
    provider = _StubProvider(
        [
            json.dumps(
                {
                    "reply": "Hier ist ein Vorschlag.",
                    "slots": {"name": "Der See", "tags": ["neu"]},
                    "relations": [{"target": "Haus", "type": "located_in"}],
                    "suggestion": "Eine Wächterin, die den See bewacht.",
                },
                ensure_ascii=False,
            )
        ]
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": "Keine Ahnung", "act": "no-idea"},
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json()["proposal"] == proposal
    assert detail.json()["proposal"] == proposal
    assert response.json()["suggestion"] == "Eine Wächterin, die den See bewacht."
    assistant = detail.json()["turns"][-1]
    assert assistant["role"] == "assistant"
    assert assistant["suggestion"] == "Eine Wächterin, die den See bewacht."
    assert assistant["suggestion_state"] == "pending"


@pytest.mark.usefixtures("two_users")
async def test_accept_and_reject_settle_the_suggestion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Accept marks the pending turn accepted (with a model call); reject settles it silently."""
    novel = await _seed_novel()
    accept_id = await _seed_session(novel)
    await _seed_suggestion(accept_id)
    reject_id = await _seed_session(novel)
    await _seed_suggestion(reject_id)
    accept_provider = _StubProvider(echo=True)
    reject_provider = _StubProvider(echo=True)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(accept_provider))

    async with _client() as client:
        accepted = await client.post(
            f"/api/chat/sessions/{accept_id}/turns",
            json={"text": "Vielleicht Mira.", "act": "accept-suggestion"},
        )
        monkeypatch.setattr(interviews, "resolve_provider", _resolving(reject_provider))
        rejected = await client.post(
            f"/api/chat/sessions/{reject_id}/turns",
            json={"text": "Vielleicht Mira.", "act": "reject-suggestion"},
        )

    assert accepted.status_code == 200
    assert accepted.json()["reply"] == "Notiert."
    accepted_turns = await _stored_turns(accept_id)
    assert [(turn.seq, turn.role, turn.act, turn.suggestion_state) for turn in accepted_turns] == [
        (1, "assistant", None, "accepted"),
        (2, "user", "accept-suggestion", None),
        (3, "assistant", None, None),
    ]
    assert len(accept_provider.requests) == 1

    assert rejected.status_code == 200
    assert rejected.json()["reply"] is None
    rejected_turns = await _stored_turns(reject_id)
    assert [(turn.seq, turn.role, turn.act, turn.suggestion_state) for turn in rejected_turns] == [
        (1, "assistant", None, "rejected"),
        (2, "user", "reject-suggestion", None),
    ]
    assert reject_provider.requests == []


@pytest.mark.usefixtures("two_users")
@pytest.mark.parametrize("text", ["Vielleicht Mira.", ""], ids=["match", "empty"])
async def test_accept_stores_the_settled_suggestion_text(
    text: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The suggestion's own text is stored, whether the client echoes it or sends none."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    await _seed_suggestion(session_id, "Vielleicht Mira.")
    provider = _StubProvider(echo=True)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": text, "act": "accept-suggestion"},
        )

    assert response.status_code == 200, response.text
    turns = await _stored_turns(session_id)
    assert [(turn.seq, turn.role, turn.text) for turn in turns] == [
        (1, "assistant", "Wie heißt sie?"),
        (2, "user", "Vielleicht Mira."),
        (3, "assistant", "Notiert."),
    ]
    assert turns[0].suggestion_state == "accepted"
    assert f"{USER_PREFIX}Vielleicht Mira." in _user_prompt(provider.requests[0])


@pytest.mark.usefixtures("two_users")
async def test_accept_with_a_mismatched_text_is_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client text that is not the pending suggestion is refused before any call."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    await _seed_suggestion(session_id, "Vielleicht Mira.")
    provider = _StubProvider(echo=True)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": "Etwas anderes", "act": "accept-suggestion"},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "suggestion-mismatch"
    turns = await _stored_turns(session_id)
    assert [(turn.seq, turn.role) for turn in turns] == [(1, "assistant")]
    assert turns[0].suggestion_state == "pending"
    assert provider.requests == []


@pytest.mark.usefixtures("two_users")
async def test_accept_refuses_when_another_suggestion_became_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A suggestion stored during the call is never accepted under an answer prepared for another.

    Step 1 settles on the pending suggestion's text and ``seq``; the provider
    stores a newer pending suggestion while the answer is generated; step 3
    finds that its own turn is no longer the pending one and refuses. The
    transcript, the proposal and the older suggestion stand untouched, and the
    completed call's audit row tells that refusal.
    """
    novel = await _seed_novel()
    session_id = await _seed_session(novel, proposal=_proposal(name="Mira"))
    await _seed_suggestion(session_id, "Vielleicht Mira.")
    provider = _NewSuggestionProvider(session_id, "Vielleicht Jona.")
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": "", "act": "accept-suggestion"},
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "suggestion-mismatch"
    turns = await _stored_turns(session_id)
    assert [
        (turn.seq, turn.role, turn.text, turn.suggestion, turn.suggestion_state) for turn in turns
    ] == [
        (1, "assistant", "Wie heißt sie?", "Vielleicht Mira.", "pending"),
        (2, "assistant", "Noch eine Frage?", "Vielleicht Jona.", "pending"),
    ]
    assert detail.json()["proposal"] == _proposal(name="Mira")
    rows = await _audit_details()
    assert [(row["status"], row["error_code"]) for row in rows] == [
        ("error", "suggestion-mismatch"),
    ]
    assert len(provider.requests) == 1


@pytest.mark.usefixtures("two_users")
async def test_drop_suggestions_removes_the_marked_parts_and_keeps_the_rest() -> None:
    """Every suggested slot and relation leaves; what the writer said stays."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel,
        proposal=_proposal(
            name="Mira",
            name_suggested=True,
            aliases=["Die Wächterin"],
            tags=["wachsam"],
            content="Eine Wächterin am See.",
            suggested={"aliases": [], "tags": ["wachsam"], "content": True},
            relations=[
                {"target": "Haus", "type": "located_in", "note": "", "suggested": True},
                {"target": "See", "type": "near", "note": "", "suggested": False},
            ],
        ),
    )

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": "Vorschläge verwerfen", "act": "drop-suggestions"},
        )

    assert response.status_code == 200
    assert response.json()["proposal"] == _proposal(
        aliases=["Die Wächterin"],
        relations=[{"target": "See", "type": "near", "note": "", "suggested": False}],
    )
    turns = await _stored_turns(session_id)
    assert [(turn.seq, turn.role, turn.act) for turn in turns] == [(1, "user", "drop-suggestions")]


@pytest.mark.usefixtures("two_users")
async def test_dropping_every_suggestion_stores_no_proposal() -> None:
    """A proposal whose every part was suggested drops to ``None``, not an empty object."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel,
        proposal=_proposal(
            name="Mira",
            name_suggested=True,
            aliases=["Die Wächterin"],
            tags=["wachsam"],
            content="Eine Wächterin am See.",
            suggested={"aliases": ["Die Wächterin"], "tags": ["wachsam"], "content": True},
            relations=[
                {"target": "Haus", "type": "located_in", "note": "", "suggested": True},
            ],
        ),
    )

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": "Vorschläge verwerfen", "act": "drop-suggestions"},
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json()["proposal"] is None
    assert detail.json()["proposal"] is None


@pytest.mark.usefixtures("two_users")
async def test_reject_and_drop_make_no_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two acts without a model answer from the stored session alone."""
    novel = await _seed_novel()
    reject_id = await _seed_session(novel)
    await _seed_suggestion(reject_id)
    drop_id = await _seed_session(novel)
    provider = _FailingProvider(RuntimeError("the model must not be called"))
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        rejected = await client.post(
            f"/api/chat/sessions/{reject_id}/turns",
            json={"text": "Verwerfen", "act": "reject-suggestion"},
        )
        dropped = await client.post(
            f"/api/chat/sessions/{drop_id}/turns",
            json={"text": "Vorschläge verwerfen", "act": "drop-suggestions"},
        )

    assert rejected.status_code == 200
    assert dropped.status_code == 200
    assert provider.requests == []


@pytest.mark.usefixtures("two_users")
async def test_a_foreign_session_answers_the_absent_404() -> None:
    """A turn, a read and a close on another user's session answer the absent 404.

    The bodies are byte-identical, detail included: the answer cannot tell the
    two apart.
    """
    foreign_novel = await _seed_novel(user_id=OTHER_USER)
    foreign_id = await _seed_session(foreign_novel, user_id=OTHER_USER)

    async with _client() as client:
        foreign = [
            await client.get(f"/api/chat/sessions/{foreign_id}"),
            await client.post(f"/api/chat/sessions/{foreign_id}/turns", json={"text": "Hallo"}),
            await client.post(f"/api/chat/sessions/{foreign_id}/close"),
        ]
        absent_id = uuid4()
        absent = [
            await client.get(f"/api/chat/sessions/{absent_id}"),
            await client.post(f"/api/chat/sessions/{absent_id}/turns", json={"text": "Hallo"}),
            await client.post(f"/api/chat/sessions/{absent_id}/close"),
        ]

    assert [response.status_code for response in (*foreign, *absent)] == [404] * 6
    assert [response.json() for response in foreign] == [response.json() for response in absent]
    assert all(response.json()["detail"]["code"] == "not-found" for response in (*foreign, *absent))


@pytest.mark.usefixtures("two_users")
async def test_fill_all_on_a_complete_proposal_changes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing left to suggest: fill-all keeps every value and every mark."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel, proposal=COMPLETE)
    provider = _StubProvider(echo=True)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": "Alles vorschlagen lassen", "act": "fill-all"},
        )

    assert response.status_code == 200
    assert response.json()["proposal"] == COMPLETE


@pytest.mark.usefixtures("two_users")
async def test_two_turns_in_parallel_land_with_distinct_seq_and_keep_both_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two racing turns serialize on the lock: four distinct rows, both answers kept."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel, proposal=_proposal(name="Mira"))
    provider = _RacingProvider()
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        first, second = await asyncio.gather(
            client.post(f"/api/chat/sessions/{session_id}/turns", json={"text": "Ein Alias."}),
            client.post(f"/api/chat/sessions/{session_id}/turns", json={"text": "Ein Schlagwort."}),
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert first.status_code == 200
    assert second.status_code == 200
    turns = detail.json()["turns"]
    assert [turn["seq"] for turn in turns] == [1, 2, 3, 4]
    assert [turn["role"] for turn in turns] == ["user", "assistant", "user", "assistant"]
    proposal = detail.json()["proposal"]
    assert "Die Wächterin" in proposal["aliases"]
    assert "wachsam" in proposal["tags"]
    assert proposal["name"] == "Mira"


@pytest.mark.usefixtures("two_users")
async def test_two_turns_racing_on_one_list_slot_keep_both_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both racing aliases survive: the merge unions the slot, never replaces it."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel, proposal=_proposal(name="Mira"))
    provider = _AliasRacingProvider()
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        first, second = await asyncio.gather(
            client.post(f"/api/chat/sessions/{session_id}/turns", json={"text": "Ein Alias."}),
            client.post(f"/api/chat/sessions/{session_id}/turns", json={"text": "Noch ein Alias."}),
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert first.status_code == 200
    assert second.status_code == 200
    proposal = detail.json()["proposal"]
    assert set(proposal["aliases"]) == {"Die Wächterin", "Die Hüterin"}
    assert proposal["name"] == "Mira"


@pytest.mark.usefixtures("two_users")
async def test_a_list_merge_takes_the_answers_changes_not_its_whole_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One item dropped, one added: the untouched item and the answer's change are exact."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel, proposal=_proposal(aliases=["A", "B"]))
    answer = json.dumps(
        {
            "reply": "Notiert.",
            "slots": {"aliases": ["A", "C"]},
            "relations": [],
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Zwei Aliasse."}
        )

    assert response.status_code == 200
    assert response.json()["proposal"]["aliases"] == ["A", "C"]
    assert response.json()["proposal"]["suggested"]["aliases"] == []


@pytest.mark.usefixtures("two_users")
async def test_a_case_only_restatement_keeps_its_mark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """«mira» restates «Mira»: identity is case-insensitive, so spelling and mark stay."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel,
        proposal=_proposal(
            name="Die Wächterin",
            aliases=["Mira"],
            suggested={"aliases": ["Mira"], "tags": [], "content": False},
        ),
    )
    answer = json.dumps(
        {
            "reply": "Notiert.",
            "slots": {"aliases": ["mira"]},
            "relations": [],
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt mira."}
        )

    assert response.status_code == 200
    assert response.json()["proposal"]["aliases"] == ["Mira"]
    assert response.json()["proposal"]["suggested"]["aliases"] == ["Mira"]


@pytest.mark.usefixtures("two_users")
async def test_an_answer_without_relations_leaves_them_in_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An omitted relations key is untouched, provenance included: no list, no drops."""
    novel = await _seed_novel()
    relations = [
        {"target": "Haus", "type": "located_in", "note": "", "suggested": False},
        {"target": "See", "type": "near", "note": "bei Nacht", "suggested": True},
    ]
    session_id = await _seed_session(
        novel, proposal=_proposal(name="Mira", relations=[dict(row) for row in relations])
    )
    answer = json.dumps({"reply": "Notiert.", "slots": {"name": "Mira"}}, ensure_ascii=False)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )

    assert response.status_code == 200
    assert response.json()["proposal"]["relations"] == relations


@pytest.mark.usefixtures("two_users")
async def test_a_relation_list_drops_only_the_one_it_omits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A given list is the answer's changes: the relation it omits leaves, the rest stays."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel,
        proposal=_proposal(
            name="Mira",
            relations=[
                {"target": "Haus", "type": "located_in", "note": "", "suggested": False},
                {"target": "See", "type": "near", "note": "", "suggested": True},
            ],
        ),
    )
    answer = json.dumps(
        {
            "reply": "Notiert.",
            "slots": {"name": "Mira"},
            "relations": [{"target": "Haus", "type": "located_in", "note": ""}],
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Nur das Haus."}
        )

    assert response.status_code == 200
    assert response.json()["proposal"]["relations"] == [
        {"target": "Haus", "type": "located_in", "note": "", "suggested": False},
    ]


@pytest.mark.usefixtures("two_users")
@pytest.mark.parametrize("empty", ["", None], ids=["empty-string", "null"])
async def test_a_cleared_name_leaves_the_proposal_unready(
    empty: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A name given "" or null clears the slot; the rest of the proposal stays."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel, proposal=_proposal(name="Mira", content="Eine Wächterin am See.")
    )
    answer = json.dumps({"reply": "Ohne Namen.", "slots": {"name": empty}}, ensure_ascii=False)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Den Namen doch nicht."}
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["name"] is None
    assert proposal["content"] == "Eine Wächterin am See."


@pytest.mark.usefixtures("two_users")
async def test_clearing_every_alias_empties_the_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty alias list drops every alias its input carried, marks included."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel,
        proposal=_proposal(
            name="Mira",
            aliases=["Die Wächterin", "Mira"],
            suggested={"aliases": ["Mira"], "tags": [], "content": False},
        ),
    )
    answer = json.dumps({"reply": "Keine Aliasse.", "slots": {"aliases": []}}, ensure_ascii=False)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Keine anderen Namen."}
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["aliases"] == []
    assert proposal["suggested"]["aliases"] == []
    assert proposal["name"] == "Mira"


@pytest.mark.usefixtures("two_users")
async def test_clearing_the_content_unsets_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A content given "" clears the body and its suggested mark."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel,
        proposal=_proposal(
            name="Mira",
            content="Eine Wächterin am See.",
            suggested={"aliases": [], "tags": [], "content": True},
        ),
    )
    answer = json.dumps(
        {"reply": "Ohne Beschreibung.", "slots": {"content": ""}}, ensure_ascii=False
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Die Beschreibung weg."}
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["content"] == ""
    assert proposal["suggested"]["content"] is False


@pytest.mark.usefixtures("two_users")
async def test_an_empty_name_does_not_erase_a_name_another_turn_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A's input carried no name, so A's empty echo leaves B's «Mira» and its mark."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    provider = _ConcurrentSaveProvider(
        session_id,
        _proposal(name="Mira", name_suggested=True),
        {"name": ""},
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Wie heißt sie?"}
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["name"] == "Mira"
    assert proposal["name_suggested"] is True


@pytest.mark.usefixtures("two_users")
async def test_an_empty_content_does_not_erase_a_content_another_turn_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A's input carried no content, so A's empty echo leaves B's content and its mark."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    provider = _ConcurrentSaveProvider(
        session_id,
        _proposal(
            content="Eine Wächterin am See.",
            suggested={"aliases": [], "tags": [], "content": True},
        ),
        {"content": ""},
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Erzähl mir von ihr."}
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["content"] == "Eine Wächterin am See."
    assert proposal["suggested"]["content"] is True


@pytest.mark.usefixtures("two_users")
async def test_an_empty_name_still_clears_one_its_input_carried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A's input carried «Mira», so A's empty echo is a real clear, B's «Vera» included."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel, proposal=_proposal(name="Mira"))
    provider = _ConcurrentSaveProvider(session_id, _proposal(name="Vera"), {"name": ""})
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Den Namen doch nicht."}
        )

    assert response.status_code == 200
    assert response.json()["proposal"] is None


@pytest.mark.usefixtures("two_users")
async def test_an_unchanged_list_echo_does_not_resurrect_an_item_another_turn_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A's input carried «A»; B's plain turn dropped it; A's echo leaves it gone."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel, proposal=_proposal(name="Mira", aliases=["A"]))
    provider = _ConcurrentTurnProvider(
        session_id,
        act=None,
        b_answer=json.dumps({"reply": "Weg damit.", "slots": {"aliases": []}}, ensure_ascii=False),
        a_answer=json.dumps({"reply": "Notiert.", "slots": {"aliases": ["A"]}}, ensure_ascii=False),
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Noch ein Alias."}
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["aliases"] == []
    assert proposal["suggested"]["aliases"] == []
    assert proposal["name"] == "Mira"


@pytest.mark.usefixtures("two_users")
async def test_an_unchanged_list_echo_under_fill_all_does_not_resurrect_it_as_suggested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A's fill-all echo must not bring back, marked suggested, an item B removed."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel, proposal=_proposal(name="Mira", aliases=["A"]))
    provider = _ConcurrentTurnProvider(
        session_id,
        act=None,
        b_answer=json.dumps({"reply": "Weg damit.", "slots": {"aliases": []}}, ensure_ascii=False),
        a_answer=json.dumps(
            {"reply": "Alles vorgeschlagen.", "slots": {"aliases": ["A"]}}, ensure_ascii=False
        ),
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": "Alles vorschlagen lassen", "act": "fill-all"},
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["aliases"] == []
    assert proposal["suggested"]["aliases"] == []
    assert proposal["name"] == "Mira"


@pytest.mark.usefixtures("two_users")
async def test_an_unchanged_list_echo_does_not_resurrect_a_dropped_suggestion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B drops suggestions, «A» with its mark; A's unchanged echo leaves it gone."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel,
        proposal=_proposal(
            name="Mira",
            aliases=["A"],
            suggested={"aliases": ["A"], "tags": [], "content": False},
        ),
    )
    provider = _ConcurrentTurnProvider(
        session_id,
        act="drop-suggestions",
        b_answer=None,
        a_answer=json.dumps({"reply": "Notiert.", "slots": {"aliases": ["A"]}}, ensure_ascii=False),
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Noch ein Alias."}
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["aliases"] == []
    assert proposal["suggested"]["aliases"] == []
    assert proposal["name"] == "Mira"


@pytest.mark.usefixtures("two_users")
async def test_an_omitted_slot_is_still_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the key the answer gives moves: name, aliases and content keep their values."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel,
        proposal=_proposal(
            name="Mira", aliases=["Die Wächterin"], content="Eine Wächterin am See."
        ),
    )
    answer = json.dumps({"reply": "Notiert.", "slots": {"tags": ["wachsam"]}}, ensure_ascii=False)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie ist wachsam."}
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["name"] == "Mira"
    assert proposal["aliases"] == ["Die Wächterin"]
    assert proposal["content"] == "Eine Wächterin am See."
    assert proposal["tags"] == ["wachsam"]


@pytest.mark.usefixtures("two_users")
async def test_two_relations_to_one_target_with_different_types_both_survive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relation's merge identity is its target and type, so both rows stay."""
    novel = await _seed_novel()
    session_id = await _seed_session(
        novel,
        proposal=_proposal(
            name="Mira",
            relations=[
                {"target": "Haus", "type": "located_in", "note": "", "suggested": False},
            ],
        ),
    )
    answer = json.dumps(
        {
            "reply": "Notiert.",
            "slots": {"name": "Mira"},
            "relations": [
                {"target": "Haus", "type": "located_in", "note": ""},
                {"target": "Haus", "type": "guards", "note": "seit Jahren"},
            ],
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie bewacht das Haus."}
        )

    assert response.status_code == 200
    relations = response.json()["proposal"]["relations"]
    assert [(relation["target"], relation["type"]) for relation in relations] == [
        ("Haus", "located_in"),
        ("Haus", "guards"),
    ]


@pytest.mark.usefixtures("two_users")
async def test_a_long_model_name_is_cut_to_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model name over the limit is cut to 200, not refused and not stored whole."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    provider = _StubProvider(
        [
            json.dumps(
                {"reply": "Notiert.", "slots": {"name": "L" * 250}, "relations": []},
                ensure_ascii=False,
            )
        ]
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Ihr Name ist lang."}
        )

    assert response.status_code == 200
    assert len(response.json()["proposal"]["name"]) == 200


@pytest.mark.usefixtures("two_users")
async def test_unparseable_twice_is_502_with_two_audit_rows_and_no_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two unreadable answers leave the named 502, two audit rows and no turn."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    provider = _StubProvider(["this is prose, not JSON {{", "and again, prose"])
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "extraction-failed"
    assert len(provider.requests) == 2
    assert detail.json()["turns"] == []
    assert detail.json()["proposal"] is None
    assert await _audit_rows() == [
        ("chat.ask", "knowledge.entity-interview", "error"),
        ("chat.ask", "knowledge.entity-interview", "error"),
    ]
    rows = await _audit_details()
    assert [row["error_code"] for row in rows] == ["extraction-failed", "extraction-failed"]
    assert all(row["error"] for row in rows)


@pytest.mark.usefixtures("two_users")
@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("no provider is configured for chat.ask"),
        ValueError("provider carries unknown kind 'mystery'"),
        KeyUnavailableError("the keychain no longer holds the key"),
    ],
    ids=["runtime", "value", "key-unavailable"],
)
async def test_provider_missing_is_502_provider_unavailable(
    failure: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cascade with no serving tier answers the reason it carried; nothing is written."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)

    async def missing(session: AsyncSession, user_id: UUID, task_key: str) -> ResolvedProvider:
        raise failure

    monkeypatch.setattr(interviews, "resolve_provider", missing)

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "provider-unavailable",
        "detail": str(failure),
    }
    assert detail.json()["turns"] == []
    assert await _audit_rows() == []


@pytest.mark.usefixtures("two_users")
@pytest.mark.parametrize(
    "failure",
    [RuntimeError("the provider died"), TimeoutError("the provider timed out")],
    ids=["runtime", "timeout"],
)
async def test_provider_error_is_502_provider_error(
    failure: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A provider that fails mid-call names its class; the turn writes nothing."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    provider = _FailingProvider(failure, delay=0.01)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "provider-error"
    assert type(failure).__name__ in response.json()["detail"]["detail"]
    assert detail.json()["turns"] == []
    assert await _audit_rows() == [("chat.ask", "knowledge.entity-interview", "error")]
    [row] = await _audit_details()
    assert row["error_code"] == "provider-error"
    assert str(failure) in cast("str", row["error"])
    assert row["response_text"] == ""
    assert cast("str", row["prompt_text"])
    # The attempt slept 10 ms before raising: its row carries the measured time,
    # never the constant zero a missing measurement wrote.
    assert cast("int", row["latency_ms"]) >= 5


@pytest.mark.usefixtures("two_users")
async def test_a_malformed_first_attempt_keeps_its_own_audit_beside_a_raising_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The completed malformed attempt is extraction-failed, not the retry's provider-error."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    provider = _MalformedThenFailingProvider(RuntimeError("the retry died"))
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "provider-error"
    assert detail.json()["turns"] == []
    assert detail.json()["proposal"] is None
    rows = await _audit_details()
    by_answer = {cast("str", row["response_text"]): row for row in rows}
    malformed = by_answer["this is prose, not JSON {{"]
    failed = by_answer[""]
    assert (malformed["status"], malformed["error_code"]) == ("error", "extraction-failed")
    assert "reply" in cast("str", malformed["error"])
    assert (failed["status"], failed["error_code"]) == ("error", "provider-error")
    assert "the retry died" in cast("str", failed["error"])


@pytest.mark.usefixtures("two_users")
async def test_closed_session_refuses_a_turn_with_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closed interview refuses the turn in step one, before any model call."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel, proposal=COMPLETE, closed=True)
    provider = _StubProvider(echo=True)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "session-closed"
    assert detail.json()["turns"] == []
    assert provider.requests == []


@pytest.mark.usefixtures("two_users")
async def test_a_closed_session_answers_409_before_a_suggestion_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closed outranks a mismatch: the suggestion stays pending and no call runs."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel, closed=True)
    await _seed_suggestion(session_id, "Vielleicht Mira.")
    provider = _StubProvider(echo=True)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": "Etwas anderes", "act": "accept-suggestion"},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "session-closed"
    turns = await _stored_turns(session_id)
    assert [(turn.seq, turn.role) for turn in turns] == [(1, "assistant")]
    assert turns[0].suggestion_state == "pending"
    assert provider.requests == []


@pytest.mark.usefixtures("two_users")
async def test_close_is_idempotent() -> None:
    """Closing twice answers the same closed session; the first stamp stands."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)

    async with _client() as client:
        first = await client.post(f"/api/chat/sessions/{session_id}/close")
        second = await client.post(f"/api/chat/sessions/{session_id}/close")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["closed_at"] is not None
    assert second.json()["closed_at"] == first.json()["closed_at"]


@pytest.mark.usefixtures("two_users")
async def test_a_close_between_the_read_and_the_write_answers_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A session closed while the model answered is the coded 409, not a 500.

    Step 1 read the session as open; the provider then closes it from a second
    session; step 3's lock sees the close, rolls back and writes the completed
    call's audit row without touching the expired locked row.
    """
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    provider = _ClosingProvider(session_id)
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "session-closed"
    assert len(provider.requests) == 1
    assert detail.json()["turns"] == []
    assert detail.json()["closed_at"] is not None
    assert await _audit_rows() == [("chat.ask", "knowledge.entity-interview", "error")]
    [row] = await _audit_details()
    assert row["error_code"] == "session-closed"


@pytest.mark.usefixtures("two_users")
async def test_a_refused_prompt_answers_502_prompt_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An override that no longer renders is a named 502, never a bare 500."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    await _save_override(interviews.INTERVIEW_KEY, "{{ not_a_variable }}", novel.id)
    provider = _StubProvider([])
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "prompt-refused"
    assert "undefined-variable" in response.json()["detail"]["detail"]
    assert provider.requests == []
    assert detail.json()["turns"] == []
    assert await _audit_rows() == []


@pytest.mark.usefixtures("two_users")
async def test_fill_all_marks_only_the_alias_the_model_adds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fill-all appends one alias: only that alias is suggested, the writer's keeps its mark."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel, proposal=_proposal(aliases=["Die Wächterin"]))
    answer = json.dumps(
        {
            "reply": "Noch ein Name.",
            "slots": {"aliases": ["Die Wächterin", "Die Hüterin"]},
            "relations": [],
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": "Alles vorschlagen lassen", "act": "fill-all"},
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["aliases"] == ["Die Wächterin", "Die Hüterin"]
    assert proposal["suggested"] == {
        "aliases": ["Die Hüterin"],
        "tags": [],
        "content": False,
    }


@pytest.mark.usefixtures("two_users")
async def test_a_turn_that_changes_nothing_keeps_the_proposal_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An answer with no slots leaves ``proposal`` null; it never becomes an empty object."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    provider = _StubProvider(
        [
            json.dumps(
                {"reply": "Erzähl mir mehr.", "slots": {}, "relations": []},
                ensure_ascii=False,
            )
        ]
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Ich weiß noch nichts."}
        )
        detail = await client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json()["proposal"] is None
    assert detail.json()["proposal"] is None


@pytest.mark.usefixtures("two_users")
async def test_the_model_output_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thirteen relations keep twelve; type and content cut; blank labels drop."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    answer = json.dumps(
        {
            "reply": "Alles, was ich habe.",
            "slots": {
                "aliases": ["", "   ", "Mira"],
                "tags": ["", "Wächterin"],
                "content": "x" * 10_050,
            },
            "relations": [{"target": f"Target {index}", "type": "r" * 100} for index in range(13)],
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(_StubProvider([answer])))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert len(proposal["relations"]) == 12
    assert all(len(relation["type"]) == 80 for relation in proposal["relations"])
    assert len(proposal["content"]) == 10_000
    assert proposal["aliases"] == ["Mira"]
    assert proposal["tags"] == ["Wächterin"]


@pytest.mark.usefixtures("two_users")
async def test_the_roster_cut_line_closes_the_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """More than 200 entities: the ROSTER block carries 200 lines and the cut line last."""
    novel = await _seed_novel()
    await _seed_entities(novel, 201)
    session_id = await _seed_session(novel)
    provider = _StubProvider(
        [json.dumps({"reply": "Notiert.", "slots": {}, "relations": []}, ensure_ascii=False)]
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Sie heißt Mira."}
        )

    assert response.status_code == 200
    roster = _prompt_block(_user_prompt(provider.requests[0]), "ROSTER:", "REQUEST:")
    assert len(roster) == 201
    assert roster[0] == "Entity 000 (character; none)"
    assert roster[-1] == ROSTER_CUT_LINE


@pytest.mark.usefixtures("two_users")
async def test_the_prompt_carries_the_last_twenty_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Twenty stored turns: the 21st line is the writer's current turn, the first is gone."""
    novel = await _seed_novel()
    session_id = await _seed_session(novel)
    await _seed_turns(session_id, 20)
    provider = _StubProvider(
        [json.dumps({"reply": "Notiert.", "slots": {}, "relations": []}, ensure_ascii=False)]
    )
    monkeypatch.setattr(interviews, "resolve_provider", _resolving(provider))

    async with _client() as client:
        response = await client.post(
            f"/api/chat/sessions/{session_id}/turns", json={"text": "Jetzt."}
        )

    assert response.status_code == 200
    prompt = _user_prompt(provider.requests[0])
    turns = _prompt_block(prompt, "TURNS:", "ROSTER:")
    assert len(turns) == 20
    assert turns[0] == f"{USER_PREFIX}Turn 2"
    assert turns[-1] == f"{USER_PREFIX}Jetzt."
    assert f"{USER_PREFIX}Turn 1" not in turns


@pytest.mark.usefixtures("two_users")
async def test_the_list_is_newest_first_per_state() -> None:
    """The open sessions lead, newest first; a newer closed one still follows them."""
    novel = await _seed_novel()
    ids = [await _seed_session(novel) for _ in range(3)]
    base = datetime(2026, 11, 1, 12, tzinfo=UTC)
    for offset, session_id in enumerate(ids):
        await _set_created_at(session_id, base + timedelta(minutes=offset))
    ended = await _seed_session(novel, closed=True)
    await _set_created_at(ended, base + timedelta(hours=1))

    async with _client() as client:
        response = await client.get("/api/chat/sessions", params={"novel_id": str(novel.id)})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [
        *(str(session_id) for session_id in reversed(ids)),
        str(ended),
    ]
    assert [item["closed_at"] is None for item in response.json()["items"]] == [
        True,
        True,
        True,
        False,
    ]
