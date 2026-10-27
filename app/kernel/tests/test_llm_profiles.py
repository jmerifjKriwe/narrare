"""ProviderProfile and TaskAssignment: the columns, the scoping, the cascade.

Task 3's resolver and Task 4's settings surface sit on these rows, so the
column sets are pinned here the way llm_calls' are — a drift fails at its
first commit — and the two-user cases prove the repositories stay narrowed to
their owner. Invariant logic (the default flip, the delete guard, D7) belongs
to the settings service, not here.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.kernel.db.base import Base
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.models import (
    PROFILE_KINDS,
    LlmCall,
    ProviderProfile,
    TaskAssignment,
)
from app.kernel.llm.profiles import AssignmentRepository, ProfileRepository

PROVIDER_PROFILE_COLUMNS = {
    "id",
    "user_id",
    "name",
    "kind",
    "base_url",
    "model",
    "api_key",
    "api_key_hint",
    "is_default",
    "context_window",
    "max_output_tokens",
    "temperature",
    "request_timeout",
    "created_at",
    "updated_at",
}

TASK_ASSIGNMENT_COLUMNS = {
    "id",
    "user_id",
    "task_key",
    "profile_id",
    "created_at",
    "updated_at",
}


@pytest.mark.usefixtures("schema")
def test_provider_profiles_is_registered_with_exactly_these_columns() -> None:
    """Verify the table exposes exactly the profile contract's columns."""
    table = Base.metadata.tables[ProviderProfile.__tablename__]
    assert set(table.columns.keys()) == PROVIDER_PROFILE_COLUMNS


@pytest.mark.usefixtures("schema")
def test_task_assignments_is_registered_with_exactly_these_columns() -> None:
    """Verify the table exposes exactly the assignment contract's columns."""
    table = Base.metadata.tables[TaskAssignment.__tablename__]
    assert set(table.columns.keys()) == TASK_ASSIGNMENT_COLUMNS


def test_the_kind_vocabulary_is_fake_and_openai_chat() -> None:
    """Verify PROFILE_KINDS is the closed vocabulary beside the free-text column."""
    assert PROFILE_KINDS == ("fake", "openai-chat")


OWNER = uuid4()
OTHER = uuid4()


@pytest.fixture
async def two_users(empty_tables: None, schema: None) -> None:
    """Two seeded users: one owns the rows, the other proves the narrowing.

    ``schema`` so a single-file run on a fresh test database rebuilds the
    tables before ``empty_tables`` truncates them.
    """
    await seed_user(OWNER)
    await seed_user(OTHER)


@pytest.mark.usefixtures("two_users")
async def test_profiles_persist_through_the_repository_scoped_to_their_user() -> None:
    """Verify a profile comes back through its owner's repository and no other."""
    async with Session() as session:
        await ProfileRepository(session, OWNER).create(
            name="Local fake", kind="fake", is_default=True
        )
        await ProfileRepository(session, OWNER).create(
            name="Hosted",
            kind="openai-chat",
            base_url="https://api.example.com",
            model="some-model",
            api_key="gAAAA-ciphertext",
            api_key_hint="abcd",
            context_window=128_000,
            max_output_tokens=4_096,
            temperature=0.7,
            request_timeout=30.0,
        )
        other_profile = await ProfileRepository(session, OTHER).create(
            name="Other's fake", kind="fake"
        )
        await session.commit()

    async with Session() as session:
        mine = ProfileRepository(session, OWNER)
        assert {profile.name for profile in await mine.ordered()} == {
            "Local fake",
            "Hosted",
        }
        assert await mine.get(other_profile.id) is None  # another user's id: hidden
        theirs = ProfileRepository(session, OTHER)
        assert [profile.name for profile in await theirs.ordered()] == ["Other's fake"]


@pytest.mark.usefixtures("two_users")
async def test_ordered_lists_the_default_first_then_the_names() -> None:
    """Verify the ordering contract: default first, the rest by name."""
    async with Session() as session:
        repo = ProfileRepository(session, OWNER)
        await repo.create(name="alpha", kind="fake")
        await repo.create(name="gamma", kind="fake", is_default=True)
        await repo.create(name="beta", kind="fake")
        await session.commit()

    async with Session() as session:
        names = [p.name for p in await ProfileRepository(session, OWNER).ordered()]

    assert names == ["gamma", "alpha", "beta"]


@pytest.mark.usefixtures("two_users")
async def test_update_applies_fields_and_delete_removes_the_profile() -> None:
    """Verify update changes the stored columns and delete drops the row."""
    async with Session() as session:
        repo = ProfileRepository(session, OWNER)
        profile = await repo.create(name="First", kind="fake")
        await repo.update(profile, name="Renamed", model="fake-model", temperature=0.3)
        await session.commit()
        profile_id = profile.id

    async with Session() as session:
        repo = ProfileRepository(session, OWNER)
        profile = await repo.get(profile_id)
        assert profile is not None
        assert (profile.name, profile.model, profile.temperature) == (
            "Renamed",
            "fake-model",
            0.3,
        )
        await repo.delete(profile)
        await session.commit()

    async with Session() as session:
        assert await ProfileRepository(session, OWNER).get(profile_id) is None


@pytest.mark.usefixtures("two_users")
async def test_update_refuses_ownership_and_identity_columns() -> None:
    """``user_id`` and ``id`` are not editable: passing them is a bug, not a choice."""
    async with Session() as session:
        repo = ProfileRepository(session, OWNER)
        profile = await repo.create(name="First", kind="fake")
        with pytest.raises(ValueError, match="id, user_id"):
            await repo.update(profile, user_id=uuid4(), id=uuid4())


@pytest.mark.usefixtures("two_users")
async def test_deleting_a_profile_cascades_its_assignments() -> None:
    """Verify the foreign key takes the profile's assignments with it."""
    async with Session() as session:
        profiles = ProfileRepository(session, OWNER)
        assignments = AssignmentRepository(session, OWNER)
        profile = await profiles.create(name="Doomed", kind="fake")
        await assignments.set("chat.ask", profile.id)
        await profiles.delete(profile)
        await session.commit()

    async with Session() as session:
        assert await AssignmentRepository(session, OWNER).for_task("chat.ask") is None


@pytest.mark.usefixtures("two_users")
async def test_set_points_a_task_at_a_profile_and_replaces_the_choice() -> None:
    """Verify set writes one row per task and re-points it on a second set."""
    async with Session() as session:
        profiles = ProfileRepository(session, OWNER)
        first = await profiles.create(name="First", kind="fake")
        second = await profiles.create(name="Second", kind="fake")
        assignments = AssignmentRepository(session, OWNER)
        await assignments.set("writing.continuation", first.id)
        await assignments.set("writing.continuation", second.id)  # replace, not a row
        await assignments.set("chat.ask", first.id)
        await session.commit()

    async with Session() as session:
        assignments = AssignmentRepository(session, OWNER)
        assignment = await assignments.for_task("writing.continuation")
        assert assignment is not None
        assert assignment.profile_id == second.id
        assert sorted(a.task_key for a in await assignments.list_all()) == [
            "chat.ask",
            "writing.continuation",
        ]


@pytest.mark.usefixtures("two_users")
async def test_for_prefix_matches_dotted_children_never_the_bare_key() -> None:
    """Verify a prefix lookup finds `<prefix>.…` assignments and nothing else."""
    async with Session() as session:
        profiles = ProfileRepository(session, OWNER)
        profile = await profiles.create(name="One", kind="fake")
        assignments = AssignmentRepository(session, OWNER)
        await assignments.set("writing.continuation", profile.id)
        await assignments.set("knowledge", profile.id)  # a bare key, not a prefix
        await session.commit()

    async with Session() as session:
        assignments = AssignmentRepository(session, OWNER)
        found = await assignments.for_prefix("writing")
        assert found is not None
        assert found.task_key == "writing.continuation"
        assert await assignments.for_prefix("chat") is None
        # An assignment on the bare key itself is an exact match for_task
        # owns — it never stands in for the segment's other tasks.
        assert await assignments.for_prefix("knowledge") is None


@pytest.mark.usefixtures("two_users")
async def test_clear_removes_the_assignment_and_stays_quiet_without_one() -> None:
    """Verify clear drops the user's assignment and tolerates a missing one."""
    async with Session() as session:
        profiles = ProfileRepository(session, OWNER)
        profile = await profiles.create(name="One", kind="fake")
        assignments = AssignmentRepository(session, OWNER)
        await assignments.set("chat.ask", profile.id)
        await assignments.clear("chat.ask")
        await assignments.clear("chat.ask")  # nothing there: quiet
        await session.commit()

    async with Session() as session:
        assert await AssignmentRepository(session, OWNER).for_task("chat.ask") is None


@pytest.mark.usefixtures("two_users")
async def test_assignments_are_scoped_per_user_even_for_the_same_task() -> None:
    """Verify both users can hold the same task_key without seeing each other."""
    async with Session() as session:
        mine = await ProfileRepository(session, OWNER).create(name="Mine", kind="fake")
        theirs = await ProfileRepository(session, OTHER).create(name="Theirs", kind="fake")
        await AssignmentRepository(session, OWNER).set("chat.ask", mine.id)
        await AssignmentRepository(session, OTHER).set("chat.ask", theirs.id)
        await session.commit()

    async with Session() as session:
        owner_assignment = await AssignmentRepository(session, OWNER).for_task("chat.ask")
        other_assignment = await AssignmentRepository(session, OTHER).for_task("chat.ask")
        assert owner_assignment is not None
        assert other_assignment is not None
        assert owner_assignment.profile_id == mine.id
        assert other_assignment.profile_id == theirs.id


@pytest.mark.usefixtures("two_users")
async def test_an_llm_call_row_round_trips_its_profile_id() -> None:
    """Verify the audit column carries a profile id and stays nullable."""
    async with Session() as session:
        profile = await ProfileRepository(session, OWNER).create(name="One", kind="fake")
        session.add(
            LlmCall(
                user_id=OWNER,
                task_key="a.with-profile",
                provider_kind="fake",
                model="fake",
                latency_ms=3,
                status="ok",
                prompt_text="",
                response_text="",
                profile_id=profile.id,
            )
        )
        session.add(
            LlmCall(
                user_id=OWNER,
                task_key="b.without-profile",
                provider_kind="fake",
                model="fake",
                latency_ms=3,
                status="ok",
                prompt_text="",
                response_text="",
            )
        )
        await session.commit()

    async with Session() as session:
        rows = (await session.scalars(select(LlmCall).order_by(LlmCall.task_key))).unique().all()
    assert [row.profile_id for row in rows] == [profile.id, None]
