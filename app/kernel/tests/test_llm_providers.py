"""LLMProvider and ProviderRepository: the columns, the scoping.

The provider table arrives one step ahead of its readers (plan, Task 1): the
saved endpoint a user names and tunes, which profiles then point at through
``provider_id``. The column set is pinned here the way the profile's and the
assignment's are — a drift fails at its first commit — and the repository
proves itself narrowed to its owner the way every ``ScopedRepository`` must.
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.kernel.db.base import Base
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.models import PROVIDER_KINDS, LLMProvider
from app.kernel.llm.repositories import ProfileRepository, ProviderRepository

LLM_PROVIDER_COLUMNS = {
    "id",
    "user_id",
    "name",
    "kind",
    "base_url",
    "models_url",
    "vendor",
    "api_key",
    "api_key_hint",
    "created_at",
    "updated_at",
}


@pytest.mark.usefixtures("schema")
def test_llm_providers_is_registered_with_exactly_these_columns() -> None:
    """Verify the table exposes exactly the provider contract's columns."""
    table = Base.metadata.tables[LLMProvider.__tablename__]
    assert set(table.columns.keys()) == LLM_PROVIDER_COLUMNS


def test_the_provider_kind_vocabulary_is_fake_openai_chat_and_anthropic() -> None:
    """Verify PROVIDER_KINDS is the closed vocabulary beside the free-text column."""
    assert PROVIDER_KINDS == ("fake", "openai-chat", "anthropic")


OWNER = uuid4()


@pytest.fixture
async def owner(empty_tables: None, schema: None) -> None:
    """The seeded user whose provider the test creates.

    ``schema`` so a single-file run on a fresh test database rebuilds the
    tables before ``empty_tables`` truncates them.
    """
    await seed_user(OWNER)


@pytest.mark.usefixtures("owner")
async def test_a_provider_is_created_under_its_owner() -> None:
    """Verify a provider comes back through its owner's repository and no other."""
    async with Session() as session:
        provider = await ProviderRepository(session, OWNER).create(
            name="OpenCode Go",
            kind="openai-chat",
            base_url="https://opencode.ai/inference/go/openai/v1",
            models_url=None,
            vendor="opencode-go",
            api_key="",
            api_key_hint="1234",
        )
        await session.commit()
        provider_id = provider.id

    async with Session() as session:
        found = await ProviderRepository(session, OWNER).get(provider_id)
        other = await ProviderRepository(session, uuid4()).get(provider_id)

    assert found is not None
    assert found.name == "OpenCode Go"
    assert found.vendor == "opencode-go"
    assert other is None  # a user who owns nothing cannot name the row


@pytest.mark.usefixtures("owner")
async def test_deleting_a_provider_models_point_at_is_refused_at_the_database() -> None:
    """The provider FK is RESTRICT: the delete guard's atomic backstop.

    The settings service's guard answers the named 409 first; behind it the
    database is the last word — a model pointer the guard cannot see
    refuses the delete with an IntegrityError instead of cascading away
    silently. The pointer and the provider both outlive the refused delete.
    """
    async with Session() as session:
        providers = ProviderRepository(session, OWNER)
        profiles = ProfileRepository(session, OWNER)
        provider = await providers.create(name="Kept", kind="fake")
        profile = await profiles.create(name="Points at it", provider_id=provider.id)
        await session.commit()
        # The ids ride the assert below; the rollback expires the rows.
        provider_id, profile_id = provider.id, profile.id
        # The repository's delete flushes the DELETE — that is where the
        # RESTRICT refuses; the commit after it never runs.
        with pytest.raises(IntegrityError):
            await providers.delete(provider)
        await session.rollback()

    async with Session() as session:
        assert await ProfileRepository(session, OWNER).get(profile_id) is not None
        assert await ProviderRepository(session, OWNER).get(provider_id) is not None


@pytest.mark.usefixtures("owner")
async def test_ordered_returns_the_users_providers_by_name_and_nobody_elses() -> None:
    """``ordered`` reads by name, the owner's rows only.

    The read is the settings list's and the provider names lookup's source,
    so a regression to insertion order — or a lost ``user_id`` scope that
    mixes a stranger's row into the list — lands unseen: until now the
    suite pinned the shape only through the API. The pin is the
    repository's own.
    """
    stranger = uuid4()
    await seed_user(stranger)
    async with Session() as session:
        await ProviderRepository(session, OWNER).create(name="Zweit", kind="fake")
        await ProviderRepository(session, OWNER).create(name="Erst", kind="fake")
        await ProviderRepository(session, stranger).create(name="AAA", kind="fake")
        await session.commit()

    async with Session() as session:
        names = [provider.name for provider in await ProviderRepository(session, OWNER).ordered()]

    assert names == ["Erst", "Zweit"]


@pytest.mark.usefixtures("owner")
async def test_update_applies_the_given_columns_and_flushes() -> None:
    """The given columns land and are durable through the caller's commit.

    The contract the services rely on: the columns update() is handed are
    applied and survive the caller's commit. The test looks only after it
    commits, so it pins neither the flush itself (a commit autoflushes
    pending writes, so a dropped flush passes here) nor the rule that the
    commit stays with the caller (an internal commit would pass here too) —
    those halves rest on the services' tests and review.
    """
    async with Session() as session:
        providers = ProviderRepository(session, OWNER)
        provider = await providers.create(name="Alt", kind="fake")
        provider_id = provider.id
        await providers.update(provider, name="Neu", base_url="https://vendor.example/v1")
        await session.commit()

    async with Session() as session:
        found = await ProviderRepository(session, OWNER).get(provider_id)

    assert found is not None
    assert (found.name, found.base_url) == ("Neu", "https://vendor.example/v1")


@pytest.mark.usefixtures("owner")
async def test_update_refuses_the_identity_columns_by_name() -> None:
    """``id`` and ``user_id`` are refused, together and spelled in the message.

    A patch that could move the row to another id or another owner is a
    caller bug, not a choice: the refusal names the columns so the bug is
    readable at its raise, and no column is applied when it fires.
    """
    async with Session() as session:
        providers = ProviderRepository(session, OWNER)
        provider = await providers.create(name="Fest", kind="fake")
        await session.commit()

        stranger = uuid4()
        with pytest.raises(ValueError, match="cannot change id"):
            await providers.update(provider, id=stranger)
        with pytest.raises(ValueError, match="cannot change user_id"):
            await providers.update(provider, user_id=stranger)
        with pytest.raises(ValueError) as refused:
            await providers.update(provider, id=stranger, user_id=stranger)
        assert str(refused.value) == "update() cannot change id, user_id"
        assert provider.name == "Fest"  # the refusal applied nothing
