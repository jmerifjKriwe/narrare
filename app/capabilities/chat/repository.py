"""Interview persistence: sessions and turns, the novel's heading, its roster.

Every query starts from the scoped base, so another user's session is absent
rather than an error and a foreign novel is invisible to the picks the dialog
makes. Chat reads the kernel's models directly and never knowledge's code: the
roster is a column-limited select of ``entities``, not a call into the
capability that writes the canon.
"""

from datetime import UTC, datetime
from uuid import UUID  # noqa: TC003

from sqlalchemy import func, select
from sqlalchemy.orm import load_only

from app.capabilities.chat.models import AssistantSession, AssistantTurn
from app.kernel.contracts.models import Entity, Novel
from app.kernel.db.base import ScopedRepository


class AssistantSessionRepository(ScopedRepository[AssistantSession]):
    """One user's interviews: open, list, lock, append turns and close."""

    model = AssistantSession

    def _turns(self):
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

    async def list_for_novel(self, novel_id: UUID) -> list[AssistantSession]:
        """This user's sessions in the novel, newest first."""
        result = await self.session.scalars(
            self.query()
            .where(AssistantSession.novel_id == novel_id)
            .order_by(AssistantSession.created_at.desc())
        )
        return list(result.all())

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
        """The next free position, read inside the caller's locked transaction."""
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
        """Flush one turn for this user without committing the transaction."""
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
            .order_by(Entity.name)
            .limit(limit)
        )
        return list(result.all())


class NovelRepository(ScopedRepository[Novel]):
    """The novel the interview hangs off: its existence and its heading."""

    model = Novel

    async def exists(self, novel_id: UUID) -> bool:
        """Whether this user owns the novel, without loading the row."""
        found = await self.session.scalar(
            select(Novel.id).where(self.owned(), Novel.id == novel_id)
        )
        return found is not None

    async def heading(self, novel_id: UUID) -> tuple[str, str | None]:
        """The title and the genre the prompt renders, scoped to this user.

        Absent and foreign are the same refusal the service's ``not-found``
        makes; a caller that needs to answer 404 asks :meth:`exists` first.
        """
        row = (
            await self.session.execute(
                select(Novel.title, Novel.genre).where(self.owned(), Novel.id == novel_id)
            )
        ).one_or_none()
        if row is None:
            raise LookupError(f"novel {novel_id} is not visible to this user")
        return row.title, row.genre
