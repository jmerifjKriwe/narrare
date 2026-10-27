"""Repositories for provider profiles and their per-task assignments.

No invariant logic lives here — the default flip and the delete guard are the
settings service's (design D7), and validation of a ``kind`` is its gate too.
These are the narrowed reads and writes that WP2a's resolver (T3) and the
settings HTTP surface (T4) build on; the commit always stays with the caller.
"""

from collections.abc import Sequence  # noqa: TC003
from typing import Any
from uuid import UUID  # noqa: TC003

from app.kernel.db.base import ScopedRepository
from app.kernel.llm.models import ProviderProfile, TaskAssignment


class ProfileRepository(ScopedRepository[ProviderProfile]):
    """A user's provider profiles, through the narrowed base."""

    model = ProviderProfile

    async def get(self, profile_id: UUID) -> ProviderProfile | None:
        """The user's profile by id; another user's id finds nothing."""
        return await self.session.scalar(self.query().where(ProviderProfile.id == profile_id))

    async def ordered(self) -> Sequence[ProviderProfile]:
        """Every profile of the user's: the default first, then by name."""
        result = await self.session.scalars(
            self.query().order_by(ProviderProfile.is_default.desc(), ProviderProfile.name)
        )
        return result.all()

    async def create(self, **fields: Any) -> ProviderProfile:
        """Flush a new profile with the given columns, leaving the commit alone."""
        profile = ProviderProfile(user_id=self.user_id, **fields)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def update(self, profile: ProviderProfile, **fields: Any) -> ProviderProfile:
        """Apply the given columns and flush, leaving the commit alone."""
        for field, value in fields.items():
            setattr(profile, field, value)
        await self.session.flush()
        return profile

    async def delete(self, profile: ProviderProfile) -> None:
        """Remove the profile; its assignments cascade at the database."""
        await self.session.delete(profile)
        await self.session.flush()


class AssignmentRepository(ScopedRepository[TaskAssignment]):
    """A user's task-key-to-profile assignments, through the narrowed base."""

    model = TaskAssignment

    async def for_task(self, task_key: str) -> TaskAssignment | None:
        """The user's assignment for exactly this task key."""
        return await self.session.scalar(self.query().where(TaskAssignment.task_key == task_key))

    async def for_prefix(self, prefix: str) -> TaskAssignment | None:
        """The user's assignment standing in for a task segment.

        Matches assignments on ``<prefix>.…`` keys; the bare ``prefix`` itself
        never matches — that is an exact assignment :meth:`for_task` owns.
        When several assignments sit in the segment, the lowest task_key
        wins, so the stand-in is deterministic.
        """
        result = await self.session.scalars(
            self.query()
            .where(TaskAssignment.task_key.startswith(f"{prefix}."))
            .order_by(TaskAssignment.task_key)
            .limit(1)
        )
        return result.first()

    async def set(self, task_key: str, profile_id: UUID) -> TaskAssignment:
        """Point the user's task at a profile, replacing an earlier choice."""
        assignment = await self.for_task(task_key)
        if assignment is None:
            assignment = TaskAssignment(
                user_id=self.user_id, task_key=task_key, profile_id=profile_id
            )
            self.session.add(assignment)
        else:
            assignment.profile_id = profile_id
        await self.session.flush()
        return assignment

    async def clear(self, task_key: str) -> None:
        """Remove the user's assignment for the task, quietly if there is none."""
        assignment = await self.for_task(task_key)
        if assignment is not None:
            await self.session.delete(assignment)
            await self.session.flush()

    async def list_all(self) -> Sequence[TaskAssignment]:
        """Every assignment of the user's, ordered by task key."""
        result = await self.session.scalars(self.query().order_by(TaskAssignment.task_key))
        return result.all()
