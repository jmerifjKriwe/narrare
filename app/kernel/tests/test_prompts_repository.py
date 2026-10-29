"""PromptTemplate and its repository: two scopes, one override per scope.

The rows are the persistence under WP4's resolution (plan T3): a user's
override for a bundled prompt key lives either for one novel or globally,
and the database — not a service — is the last word on one global row per
key. The tests pin the semantics the repository sells: the novel row
outranks the global one, a save rewrites its scope's row instead of
stacking another, and a delete names one scope only.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.contracts.models import Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.prompts.models import PromptTemplate, PromptTemplateRepository

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


async def seed_novel(session: AsyncSession, user_id: UUID, title: str) -> Novel:
    """The novels row a novel-scoped override's foreign key reaches."""
    novel = Novel(user_id=user_id, title=title)
    session.add(novel)
    await session.flush()
    return novel


@pytest.mark.usefixtures("two_users")
async def test_two_global_rows_for_one_key_collide() -> None:
    """Verify the partial index refuses a second global row for one key.

    ``novel_id`` NULL is distinct in ``uq_prompt_templates_novel_scope``,
    so the plain constraint would let both through — the database is the
    last word, the provider-profiles pattern.
    """
    async with Session() as session:
        session.add(
            PromptTemplate(user_id=OWNER, novel_id=None, prompt_key="chat.ask", content="a")
        )
        session.add(
            PromptTemplate(user_id=OWNER, novel_id=None, prompt_key="chat.ask", content="b")
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.usefixtures("two_users")
async def test_global_and_novel_rows_coexist_for_one_key() -> None:
    """Verify the two scopes are two rows: no constraint reads across them."""
    async with Session() as session:
        novel = await seed_novel(session, OWNER, "One")
        novel_id = novel.id
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("chat.ask", "global words", None)
        await repo.save("chat.ask", "novel words", novel_id)
        await session.commit()

    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        novel_row = await repo.effective("chat.ask", novel_id)
        assert novel_row is not None
        assert novel_row.content == "novel words"
        global_row = await repo.effective("chat.ask", None)
        assert global_row is not None
        assert global_row.content == "global words"


@pytest.mark.usefixtures("two_users")
async def test_effective_prefers_the_novel_row_then_global_then_none() -> None:
    """Verify the resolution order the later override chain relies on.

    A novel without its own row falls back to the global tier; a key
    nobody overrode finds nothing at either scope.
    """
    async with Session() as session:
        overridden = await seed_novel(session, OWNER, "Overridden")
        quiet = await seed_novel(session, OWNER, "Quiet")
        repo = PromptTemplateRepository(session, OWNER)
        global_row = await repo.save("chat.ask", "global words", None)
        novel_row = await repo.save("chat.ask", "novel words", overridden.id)
        await session.commit()
        global_id, novel_id = global_row.id, novel_row.id

    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        found = await repo.effective("chat.ask", overridden.id)
        assert found is not None
        assert found.id == novel_id  # the novel's own row wins
        found = await repo.effective("chat.ask", quiet.id)
        assert found is not None
        assert found.id == global_id  # the global tier stands in
        found = await repo.effective("chat.ask", None)
        assert found is not None
        assert found.id == global_id
        assert await repo.effective("knowledge.extract-entities", overridden.id) is None
        assert await repo.effective("knowledge.extract-entities", None) is None


@pytest.mark.usefixtures("two_users")
async def test_save_upserts_one_row_per_scope_in_place() -> None:
    """Verify a second save rewrites its scope's row instead of stacking one.

    ``updated_at`` moves with the rewrite — the column is the freshness
    signal, and a save that minted a new row would orphan the old one.
    """
    async with Session() as session:
        novel = await seed_novel(session, OWNER, "One")
        novel_id = novel.id
        first = await PromptTemplateRepository(session, OWNER).save("chat.ask", "first", None)
        await session.commit()

    async with Session() as session:
        second = await PromptTemplateRepository(session, OWNER).save("chat.ask", "second", None)
        await session.commit()
        assert second.id == first.id
        assert second.content == "second"
        assert second.updated_at > first.updated_at

    async with Session() as session:
        await PromptTemplateRepository(session, OWNER).save("chat.ask", "novel one", novel_id)
        await session.commit()

    async with Session() as session:
        await PromptTemplateRepository(session, OWNER).save("chat.ask", "novel two", novel_id)
        await session.commit()

    async with Session() as session:
        rows = (await session.scalars(select(PromptTemplate))).all()
        assert {(row.novel_id is None, row.content) for row in rows} == {
            (True, "second"),  # the global row: rewritten, not stacked
            (False, "novel two"),  # the novel row: rewritten, not stacked
        }


@pytest.mark.usefixtures("two_users")
async def test_delete_removes_only_its_scope_and_reports_an_absent_one() -> None:
    """Verify delete names one scope: the other tier keeps its row, and an
    absent one reports False instead of raising."""
    async with Session() as session:
        novel = await seed_novel(session, OWNER, "One")
        novel_id = novel.id
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("chat.ask", "global words", None)
        await repo.save("chat.ask", "novel words", novel_id)
        await session.commit()

    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        assert await repo.delete("chat.ask", novel_id) is True
        await session.commit()

    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        found = await repo.effective("chat.ask", novel_id)
        assert found is not None
        assert found.content == "global words"  # the global tier survived
        assert await repo.delete("chat.ask", novel_id) is False  # already gone
        assert await repo.delete("knowledge.extract-entities", None) is False  # never written


@pytest.mark.usefixtures("two_users")
async def test_repositories_stay_narrowed_to_their_user() -> None:
    """Verify one user's overrides are invisible to another user's repository.

    Two global rows for the same key must coexist across users — the
    partial index is per user — and one user's delete never reaches the
    other's row.
    """
    async with Session() as session:
        await PromptTemplateRepository(session, OWNER).save("chat.ask", "mine", None)
        await PromptTemplateRepository(session, OTHER).save("chat.ask", "theirs", None)
        await session.commit()

    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        found = await repo.effective("chat.ask", None)
        assert found is not None
        assert found.content == "mine"
        assert await repo.delete("chat.ask", None) is True
        await session.commit()

    async with Session() as session:
        found = await PromptTemplateRepository(session, OTHER).effective("chat.ask", None)
        assert found is not None
        assert found.content == "theirs"
