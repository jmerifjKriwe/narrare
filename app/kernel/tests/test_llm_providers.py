"""LLMProvider and ProviderRepository: the columns, the scoping.

The provider table arrives one step ahead of its readers (plan, Task 1): the
saved endpoint a user names and tunes, which profiles then point at through
``provider_id``. The column set is pinned here the way the profile's and the
assignment's are — a drift fails at its first commit — and the repository
proves itself narrowed to its owner the way every ``ScopedRepository`` must.
"""

from uuid import uuid4

import pytest

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


def test_the_provider_kind_vocabulary_is_fake_and_openai_chat() -> None:
    """Verify PROVIDER_KINDS is the closed vocabulary beside the free-text column."""
    assert PROVIDER_KINDS == ("fake", "openai-chat")


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
async def test_deleting_a_provider_cascades_its_profiles() -> None:
    """Verify the foreign key takes the provider's profiles with it."""
    async with Session() as session:
        providers = ProviderRepository(session, OWNER)
        profiles = ProfileRepository(session, OWNER)
        provider = await providers.create(name="Doomed", kind="fake")
        profile = await profiles.create(name="Points at it", provider_id=provider.id)
        await providers.delete(provider)
        await session.commit()
        profile_id = profile.id

    async with Session() as session:
        assert await ProfileRepository(session, OWNER).get(profile_id) is None
