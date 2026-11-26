"""Interview persistence: sessions and turns, the novel's heading, its roster.

Every query starts from the scoped base, so another user's session is absent
rather than an error and a foreign novel is invisible to the picks the dialog
makes. Chat reads the kernel's models directly and never knowledge's code: the
roster is a column-limited select of ``entities``, not a call into the
capability that writes the canon.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID  # noqa: TC003

from sqlalchemy import Select, func, literal, select
from sqlalchemy.orm import load_only

from app.capabilities.chat.models import AssistantSession, AssistantTurn
from app.kernel.contracts.models import Entity, Novel
from app.kernel.db.base import ScopedRepository

SESSION_LIST_LIMIT: Final = 200
"""How many of a novel's sessions the list returns per state: the newest, newest first.

The bound is per state, not over the whole list: the panel shows the open
interviews first, so a long history of closed ones cannot push an open session
— the door's next stop — off the wire.
"""


@dataclass(frozen=True)
class SessionListRow:
    """One list row: the session's identity and the proposal's name, no proposal.

    The panel renders a header and a state per row; the full draft is read by
    opening the session. Keeping the row small keeps the list to
    ``SESSION_LIST_LIMIT`` rows per state of fixed width instead of every
    proposal.
    """

    id: UUID
    novel_id: UUID
    mode: str
    entity_type: str | None
    target_id: UUID | None
    name: str | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AssistantSessionRepository(ScopedRepository[AssistantSession]):
    """One user's interviews: open, list, lock, append turns and close."""

    model = AssistantSession

    def _turns(self) -> Select[AssistantTurn]:
        """A turn select already narrowed to this user."""
        return select(AssistantTurn).where(AssistantTurn.user_id == self.user_id)

    async def create(
        self,
        novel_id: UUID,
        mode: str,
        entity_type: str | None,
        target_id: UUID | None,
    ) -> AssistantSession:
        """Flush a new session for this user without committing the transaction."""
        session = AssistantSession(
            user_id=self.user_id,
            novel_id=novel_id,
            mode=mode,
            entity_type=entity_type,
            target_id=target_id,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get(self, session_id: UUID) -> AssistantSession | None:
        """The session, scoped: another user's answers as absent."""
        return await self.session.scalar(self.query().where(AssistantSession.id == session_id))

    async def list_for_novel(self, novel_id: UUID) -> list[SessionListRow]:
        """This user's sessions in the novel: open first, then closed, newest first.

        The order follows the spec's surface, not the clock: the panel shows the
        open interviews before the ended ones, so the door's «newest open
        session» is the list's first row whenever one exists. Each state is
        bounded by ``SESSION_LIST_LIMIT`` on its own.

        Both states come from one statement — a ``UNION ALL`` of the two
        limited selects, the open block first — so the list is one snapshot: a
        session closed between two reads cannot match both states and appear
        twice. The name comes from the proposal JSON in the same query, so a
        list row never carries the draft.
        """
        columns = (
            AssistantSession.id,
            AssistantSession.novel_id,
            AssistantSession.mode,
            AssistantSession.entity_type,
            AssistantSession.target_id,
            AssistantSession.proposal["name"].astext.label("name"),
            AssistantSession.closed_at,
            AssistantSession.created_at,
            AssistantSession.updated_at,
        )

        def block(state: Any, rank: int) -> Any:
            """One state's newest rows, with the state's position in the list's order."""
            return (
                select(*columns, literal(rank).label("state_rank"))
                .where(self.owned(), AssistantSession.novel_id == novel_id, state)
                .order_by(AssistantSession.created_at.desc(), AssistantSession.id)
                .limit(SESSION_LIST_LIMIT)
            )

        listed = (
            block(AssistantSession.closed_at.is_(None), 0)
            .union_all(block(AssistantSession.closed_at.is_not(None), 1))
            .subquery()
        )
        result = await self.session.execute(
            select(
                listed.c.id,
                listed.c.novel_id,
                listed.c.mode,
                listed.c.entity_type,
                listed.c.target_id,
                listed.c.name,
                listed.c.closed_at,
                listed.c.created_at,
                listed.c.updated_at,
            ).order_by(listed.c.state_rank, listed.c.created_at.desc(), listed.c.id)
        )
        return [SessionListRow(*row) for row in result]

    async def lock(self, session_id: UUID) -> AssistantSession | None:
        """The session with its row lock taken (SELECT ... FOR UPDATE), scoped.

        The turn's allocation and its proposal merge happen under this lock, so
        two turns racing on one session serialize: the second waits for the
        first's commit, then allocates the next ``seq`` and merges into the
        proposal the first one left behind.
        """
        return await self.session.scalar(
            self.query().where(AssistantSession.id == session_id).with_for_update()
        )

    async def last_turns(self, session_id: UUID, limit: int) -> list[AssistantTurn]:
        """The session's most recent turns, returned oldest first.

        The model reads a bounded transcript in reading order; the query takes
        the newest ``limit`` rows and the answer reverses them.
        """
        result = await self.session.scalars(
            self._turns()
            .where(AssistantTurn.session_id == session_id)
            .order_by(AssistantTurn.seq.desc())
            .limit(limit)
        )
        return list(reversed(result.all()))

    async def next_seq(self, session_id: UUID) -> int:
        """The next free position, read inside the caller's locked transaction.

        Precondition: the caller has locked the session through :meth:`lock`
        first. This method takes a bare ``session_id`` and does not check the
        session's owner; the lock's scoped read is what proves the session is
        this user's and serializes the allocation.
        """
        highest = await self.session.scalar(
            select(func.max(AssistantTurn.seq)).where(
                AssistantTurn.user_id == self.user_id,
                AssistantTurn.session_id == session_id,
            )
        )
        return (highest or 0) + 1

    async def append_turn(
        self,
        session_id: UUID,
        seq: int,
        role: str,
        text: str,
        *,
        act: str | None = None,
        suggestion: str | None = None,
        suggestion_state: str | None = None,
    ) -> AssistantTurn:
        """Flush one turn for this user without committing the transaction.

        Precondition: the caller has locked the session through :meth:`lock`
        first. This method takes a bare ``session_id`` and does not check the
        session's owner; the lock's scoped read is what proves the session is
        this user's and serializes the ``seq`` allocation.
        """
        turn = AssistantTurn(
            user_id=self.user_id,
            session_id=session_id,
            seq=seq,
            role=role,
            text=text,
            act=act,
            suggestion=suggestion,
            suggestion_state=suggestion_state,
        )
        self.session.add(turn)
        await self.session.flush()
        return turn

    async def set_proposal(
        self, session: AssistantSession, proposal: dict[str, object] | None
    ) -> None:
        """Write the dialog's draft; the caller commits the transaction."""
        session.proposal = proposal
        await self.session.flush()

    async def set_suggestion_state(self, turn: AssistantTurn, state: str) -> None:
        """Settle a turn's suggestion; the caller commits the transaction."""
        turn.suggestion_state = state
        await self.session.flush()

    async def close(self, session: AssistantSession) -> None:
        """Stamp the session closed; the caller commits the transaction."""
        session.closed_at = datetime.now(UTC)
        await self.session.flush()


class EntityRosterRepository(ScopedRepository[Entity]):
    """The novel's entities as the interview's roster: identity words only."""

    model = Entity

    async def names_for_novel(self, novel_id: UUID, limit: int = 200) -> list[Entity]:
        """This user's entities in the novel, name-ordered, four fields only.

        The roster only needs what a line renders — ``name (type; aliases)`` —
        so the body and the search text stay in the database. The limit is the
        plan's bound on what the model sees.
        """
        result = await self.session.scalars(
            self.query()
            .options(load_only(Entity.id, Entity.name, Entity.type, Entity.aliases))
            .where(Entity.novel_id == novel_id)
            .order_by(Entity.name, Entity.id)
            .limit(limit)
        )
        return list(result.all())

    async def owns_entity(self, novel_id: UUID, entity_id: UUID) -> bool:
        """Whether this user owns the entity and it belongs to the novel.

        The door's target is a reference the session will hold, so it is
        checked through the scoped roster: another user's entity and one in a
        different novel both answer ``False``, like an absent one.
        """
        found = await self.session.scalar(
            select(Entity.id).where(
                self.owned(), Entity.novel_id == novel_id, Entity.id == entity_id
            )
        )
        return found is not None


class NovelRepository(ScopedRepository[Novel]):
    """The novel the interview hangs off: its existence and its heading."""

    model = Novel

    async def exists(self, novel_id: UUID) -> bool:
        """Whether this user owns the novel, without loading the row."""
        found = await self.session.scalar(
            select(Novel.id).where(self.owned(), Novel.id == novel_id)
        )
        return found is not None

    async def heading(self, novel_id: UUID) -> tuple[str, str | None] | None:
        """The title and the genre the prompt renders, scoped to this user.

        ``None`` covers both an absent novel and another user's, so a caller
        that needs the coded 404 tests this one result instead of a second
        round trip through :meth:`exists`.
        """
        row = (
            await self.session.execute(
                select(Novel.title, Novel.genre).where(self.owned(), Novel.id == novel_id)
            )
        ).one_or_none()
        if row is None:
            return None
        return row.title, row.genre
