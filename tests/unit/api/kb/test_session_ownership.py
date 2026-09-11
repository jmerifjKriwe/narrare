"""S7 — IDOR regression tests: ownership gate on KB creation sessions (service).

Before the S7 fix, all KB-session service verbs resolved access by bare
``session_id``: any caller could read, mutate, drive AI operations on,
complete, or delete another user's session — and ``complete_session``
persisted the resulting KB entry under the VICTIM's ``user_id``. Session
creation also accepted any ``novel_id``, letting a foreign caller open a
session against a novel they do not own.

The fix (plan S7) is two gates:
- Pattern A at the single choke point ``_get_or_raise(session_id,
  novel_id, user_id)`` — a session is only addressable by its owning
  user AND only under its own novel; foreign and unknown ids are
  indistinguishable (``NotFoundError``, never a bare ``ValueError``).
- Pattern B create-time gate: ``novel_repo.get_by_id(novel_id, user_id)``
  must return the novel BEFORE any session row exists.

Matrix (plan S7): (1) owner → flow unchanged, (2) foreign session →
NotFoundError with zero side effects (no store write, no AI call, no KB
entry), (3) unknown session → identical error shape, (4) create with
foreign/unknown novel → NotFoundError and no row, (5) complete on a
foreign session → zero KB entries for the victim.

The HTTP-level matrix (all 8 endpoints) lives in
``test_session_ownership_api.py`` (RULE-04 split).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest

from narrare.kb.session_service import KBSessionService
from narrare_core.shared.errors import NotFoundError

from ._test_fakes import make_owned_session, make_ownership_service

USER_A = uuid4()  # rightful owner of the novel + sessions (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A
OTHER_NOVEL_ID = uuid4()  # also owned by USER_A (novel-binding probe)

SESSION_NOT_FOUND = "KB creation session"


def _owned_session(name: str | None = "Aria"):
    """A session belonging to USER_A under NOVEL_ID (the victim's resource)."""
    return make_owned_session(NOVEL_ID, USER_A, name=name)


# ---------------------------------------------------------------------------
# Service level — create-time novel gate (Pattern B)
# ---------------------------------------------------------------------------


class TestCreateSessionNovelGate:
    """``create_session`` gates novel ownership before any session row."""

    async def test_owner_creates_session(self) -> None:
        service, store, _, _, novel_repo = make_ownership_service({NOVEL_ID: USER_A})

        session = await service.create_session(NOVEL_ID, USER_A, "character")

        assert session.novel_id == NOVEL_ID
        assert store.create_calls == [session.id]
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]

    async def test_foreign_novel_denied_and_no_row_created(self) -> None:
        service, store, assist, kb, novel_repo = make_ownership_service({NOVEL_ID: USER_A})

        with pytest.raises(NotFoundError, match="Novel"):
            await service.create_session(NOVEL_ID, USER_B, "character")

        assert store.create_calls == []
        assert assist.ai_calls == 0
        assert kb.created_entries == []
        # The gate ran with the CALLER's id.
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_B)]

    async def test_unknown_novel_indistinguishable_from_foreign(self) -> None:
        foreign_service, _, _, _, _ = make_ownership_service({NOVEL_ID: USER_A})
        unknown_service, _, _, _, _ = make_ownership_service({NOVEL_ID: USER_A})
        unknown_novel_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await foreign_service.create_session(NOVEL_ID, USER_B, "character")
        with pytest.raises(NotFoundError) as unknown_exc:
            await unknown_service.create_session(unknown_novel_id, USER_B, "character")

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Novel ({NOVEL_ID}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_novel_id}) not found"


# ---------------------------------------------------------------------------
# Service level — session-scoped verb matrix (Pattern A choke point)
# ---------------------------------------------------------------------------

_VerbCall = Callable[[KBSessionService, UUID, UUID, UUID], Awaitable[object]]

_VERBS: dict[str, _VerbCall] = {
    "get": lambda svc, sid, nid, uid: svc.get_session(sid, nid, uid),
    "answer_field": lambda svc, sid, nid, uid: svc.answer_field(sid, nid, uid, "name", "Aria"),
    "request_suggestion": lambda svc, sid, nid, uid: svc.request_suggestion(sid, nid, uid, "name"),
    "request_interview_question": lambda svc, sid, nid, uid: svc.request_interview_question(
        sid, nid, uid
    ),
    "request_enhancement": lambda svc, sid, nid, uid: svc.request_enhancement(sid, nid, uid),
    "complete_session": lambda svc, sid, nid, uid: svc.complete_session(sid, nid, uid),
    "abandon_session": lambda svc, sid, nid, uid: svc.abandon_session(sid, nid, uid),
}
_MUTATING_VERBS = [v for v in _VERBS if v != "get"]


class TestSessionVerbsOwnershipMatrix:
    """Every session verb is scoped to (session.novel_id, session.user_id)."""

    @pytest.mark.parametrize("verb", sorted(_VERBS))
    async def test_owner_flow_succeeds(self, verb: str) -> None:
        """Matrix case (1): the rightful owner's flow is unchanged."""
        service, store, assist, kb, _ = make_ownership_service({NOVEL_ID: USER_A})
        session = _owned_session()
        await store.create(session)

        result = await _VERBS[verb](service, session.id, NOVEL_ID, USER_A)

        if verb == "get":
            assert result is not None
        elif verb == "complete_session":
            assert kb.created_entries is not None and len(kb.created_entries) == 1
        elif verb == "abandon_session":
            assert store.delete_calls == [session.id]
        else:
            assert store.update_calls == [session.id]
            if verb.startswith("request_"):
                assert assist.ai_calls == 1

    @pytest.mark.parametrize("verb", _MUTATING_VERBS)
    async def test_foreign_session_denied_without_side_effects(self, verb: str) -> None:
        """Matrix case (2)+(4): USER_B on USER_A's session → NotFoundError
        BEFORE any write, AI call, or KB entry."""
        service, store, assist, kb, _ = make_ownership_service({NOVEL_ID: USER_A})
        session = _owned_session()
        await store.create(session)

        with pytest.raises(NotFoundError, match=SESSION_NOT_FOUND):
            await _VERBS[verb](service, session.id, NOVEL_ID, USER_B)

        assert store.update_calls == []
        assert store.delete_calls == []
        assert assist.ai_calls == 0
        assert kb.created_entries == []
        # Victim's session is untouched.
        stored = await store.get(session.id)
        assert stored is not None
        assert stored.status == "active"
        assert stored.user_id == USER_A

    async def test_get_foreign_session_returns_none(self) -> None:
        """GET shape: foreign session is indistinguishable from unknown (None)."""
        service, store, _, _, _ = make_ownership_service({NOVEL_ID: USER_A})
        session = _owned_session()
        await store.create(session)

        assert await service.get_session(session.id, NOVEL_ID, USER_B) is None
        # Owner still sees it.
        assert await service.get_session(session.id, NOVEL_ID, USER_A) is not None

    @pytest.mark.parametrize("verb", _MUTATING_VERBS)
    async def test_unknown_session_indistinguishable_from_foreign(self, verb: str) -> None:
        """Matrix case (3): unknown id → identical error type and message shape."""
        service, store, _, _, _ = make_ownership_service({NOVEL_ID: USER_A})
        victim = _owned_session()
        await store.create(victim)
        unknown_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await _VERBS[verb](service, victim.id, NOVEL_ID, USER_B)
        with pytest.raises(NotFoundError) as unknown_exc:
            await _VERBS[verb](service, unknown_id, NOVEL_ID, USER_B)

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"{SESSION_NOT_FOUND} ({victim.id}) not found"
        assert str(unknown_exc.value) == f"{SESSION_NOT_FOUND} ({unknown_id}) not found"

    async def test_get_unknown_session_returns_none(self) -> None:
        service, _, _, _, _ = make_ownership_service({NOVEL_ID: USER_A})

        assert await service.get_session(uuid4(), NOVEL_ID, USER_B) is None

    @pytest.mark.parametrize("verb", sorted(_VERBS))
    async def test_wrong_novel_in_path_denied_even_for_owner(self, verb: str) -> None:
        """A session is only addressable under its OWN novel — even the
        owner gets NotFoundError/None when the path novel does not match."""
        service, store, _, _, _ = make_ownership_service({NOVEL_ID: USER_A, OTHER_NOVEL_ID: USER_A})
        session = _owned_session()
        await store.create(session)

        if verb == "get":
            assert await _VERBS[verb](service, session.id, OTHER_NOVEL_ID, USER_A) is None
        else:
            with pytest.raises(NotFoundError, match=SESSION_NOT_FOUND):
                await _VERBS[verb](service, session.id, OTHER_NOVEL_ID, USER_A)
        assert store.update_calls == []
        assert store.delete_calls == []


class TestCompleteForeignSessionZeroWrites:
    """Plan S7 headline: attacker-driven complete → zero victim KB entries."""

    async def test_complete_on_foreign_session_writes_zero_kb_entries(self) -> None:
        service, store, assist, kb, _ = make_ownership_service({NOVEL_ID: USER_A})
        session = _owned_session(name="Aria")
        await store.create(session)

        with pytest.raises(NotFoundError, match=SESSION_NOT_FOUND):
            await service.complete_session(session.id, NOVEL_ID, USER_B)

        assert kb.created_entries == []
        assert store.update_calls == []
        stored = await store.get(session.id)
        assert stored is not None
        assert stored.status == "active"
        assert stored.user_id == USER_A
        assert assist.ai_calls == 0
