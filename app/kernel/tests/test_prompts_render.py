"""The effective-chain render: novel row, then global row, then bundled.

``render`` is the resolution glue the four prompt call sites share: the
source is the user's effective override for the scope — the novel's row,
else the global one — and the bundled template when neither exists, and
every ``{% include %}`` inside a stored override walks the same chain in
the same scope. The tests pin the chain at the database: bundled renders
when no row exists, each tier outranking the one below it, one user's
rows invisible to another's render, an include resolving the *effective*
target (override, not bundled), an unknown key a ``KeyError`` for the
caller's 404 while an unknown *include* is the named ``include-missing``
refusal — also under ``ignore missing``, which is out of contract: a
missing key is refused by name, never silently skipped — and
``syntax``/``include-depth``/``include-cycle`` flowing through the stored
path unchanged. The bridge the chain walks is pinned at both ends: a
database-shaped lookup failure passes through untranslated (an outage,
not a refusal), and a cancelled render is waited out — its include reads
finish on the live session before the cancellation is raised.
"""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.contracts.models import Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.prompts import PromptRegistry, PromptRenderError, render
from app.kernel.prompts import registry as prompts_registry
from app.kernel.prompts.models import PromptTemplate, PromptTemplateRepository

OWNER = uuid4()
OTHER = uuid4()


@pytest.fixture
def toy_registry(monkeypatch: pytest.MonkeyPatch) -> PromptRegistry:
    """A private registry, published in place of the process's one.

    The real registry is empty today — the four bundled keys dock in
    tasks 4-6 — and these tests must not leak registrations into it:
    ``monkeypatch`` swaps the singleton and restores it after each test.
    """
    registry = PromptRegistry()
    registry.register(
        "toy.ask", template="bundled ask {{ q }}", sample_variables=lambda: {"q": "s"}
    )
    registry.register("toy.frame", template="bundled frame", sample_variables=lambda: {})
    registry.register("toy.a", template="bundled a", sample_variables=lambda: {})
    registry.register("toy.b", template="bundled b", sample_variables=lambda: {})
    registry.register("toy.k6", template="END", sample_variables=lambda: {})
    for depth in range(6):
        registry.register(
            f"toy.k{depth}",
            template=f"{{% include 'toy.k{depth + 1}' %}}",
            sample_variables=lambda: {},
        )
    monkeypatch.setattr(prompts_registry, "_registry", registry)
    return registry


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


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_bundled_renders_when_no_row_exists() -> None:
    """With no override at either tier, the bundled template renders."""
    async with Session() as session:
        text = await render(session, OWNER, "toy.ask", {"q": "hi"})
    assert text == "bundled ask hi"


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_global_row_overrides_bundled() -> None:
    """A global row's content is the source, the bundled template standing down."""
    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("toy.ask", "global ask {{ q }}", None)
        await session.commit()
        text = await render(session, OWNER, "toy.ask", {"q": "hi"})
    assert text == "global ask hi"


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_novel_row_overrides_global() -> None:
    """The novel's own row wins; other novels and the bare scope fall to the global tier."""
    async with Session() as session:
        novel = await seed_novel(session, OWNER, "Overridden")
        quiet = await seed_novel(session, OWNER, "Quiet")
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("toy.frame", "global frame", None)
        await repo.save("toy.frame", "novel frame", novel.id)
        await session.commit()

        assert await render(session, OWNER, "toy.frame", {}, novel_id=novel.id) == "novel frame"
        assert await render(session, OWNER, "toy.frame", {}, novel_id=quiet.id) == "global frame"
        assert await render(session, OWNER, "toy.frame", {}) == "global frame"


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_other_users_rows_are_invisible() -> None:
    """One user's override never reaches another user's render: the chain is scoped."""
    async with Session() as session:
        await PromptTemplateRepository(session, OTHER).save("toy.ask", "theirs {{ q }}", None)
        await session.commit()
        text = await render(session, OWNER, "toy.ask", {"q": "hi"})
    assert text == "bundled ask hi"


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_include_resolves_the_effective_key() -> None:
    """A stored override's include follows the chain: the target's override, not bundled."""
    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("toy.ask", "Ask: {{ q }}; {% include 'toy.frame' %}", None)
        await repo.save("toy.frame", "FRAME-OVERRIDE", None)
        await session.commit()
        text = await render(session, OWNER, "toy.ask", {"q": "hi"})
    assert text == "Ask: hi; FRAME-OVERRIDE"


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_novel_scope_reaches_into_includes() -> None:
    """An include walks the chain at the rendering's novel scope, not bundled-only."""
    async with Session() as session:
        novel = await seed_novel(session, OWNER, "One")
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("toy.ask", "A[{% include 'toy.frame' %}]", None)
        await repo.save("toy.frame", "global frame", None)
        await repo.save("toy.frame", "novel frame", novel.id)
        await session.commit()
        text = await render(session, OWNER, "toy.ask", {}, novel_id=novel.id)
    assert text == "A[novel frame]"


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_unknown_key_is_a_key_error() -> None:
    """A key outside the closed set is the caller's ``KeyError``, before any read."""
    async with Session() as session:
        with pytest.raises(KeyError, match=r"toy\.nope"):
            await render(session, OWNER, "toy.nope", {})


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_unknown_include_refused_by_name() -> None:
    """An include of an unregistered key is ``include-missing``, not a 404-shaped error."""
    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("toy.ask", "{% include 'toy.nope' %}", None)
        await session.commit()
        with pytest.raises(PromptRenderError) as error:
            await render(session, OWNER, "toy.ask", {})
    assert error.value.reason == "include-missing"
    assert "toy.nope" in error.value.detail


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_ignore_missing_is_out_of_contract() -> None:
    """Ruled: ``ignore missing`` never fires — a missing key is refused by name.

    The loader refuses the missing key before Jinja's ignore-missing logic
    sees anything, so a stored override cannot quietly drop a section.
    """
    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("toy.ask", "{% include 'toy.nope' ignore missing %}", None)
        await session.commit()
        with pytest.raises(PromptRenderError) as error:
            await render(session, OWNER, "toy.ask", {})
    assert error.value.reason == "include-missing"


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_broken_override_is_syntax() -> None:
    """A stored template with a broken tag refuses ``syntax`` like a bundled one."""
    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("toy.ask", "Hello {% if %}!", None)
        await session.commit()
        with pytest.raises(PromptRenderError) as error:
            await render(session, OWNER, "toy.ask", {})
    assert error.value.reason == "syntax"


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_stored_chain_deeper_than_five_is_include_depth() -> None:
    """Six stored include links refuse depth: the guard sees sources from the rows too."""
    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        for depth in range(6):
            await repo.save(f"toy.k{depth}", f"{{% include 'toy.k{depth + 1}' %}}", None)
        await session.commit()
        with pytest.raises(PromptRenderError) as error:
            await render(session, OWNER, "toy.k0", {})
    assert error.value.reason == "include-depth"


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_stored_cycle_is_include_cycle() -> None:
    """``a`` → ``b`` → ``a`` through saved rows: the guard sees chains from the database."""
    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("toy.a", "{% include 'toy.b' %}", None)
        await repo.save("toy.b", "{% include 'toy.a' %}", None)
        await session.commit()
        with pytest.raises(PromptRenderError) as error:
            await render(session, OWNER, "toy.a", {})
    assert error.value.reason == "include-cycle"


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_include_lookup_failure_passes_through_untranslated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A database-shaped failure of the include lookup is an outage, not a refusal.

    The exception crosses ``Future.result()`` → worker thread → the loader's
    sentinel → ``render_source``: exactly the seam a refactor breaks, and
    breaking it would frame an outage as a refusal the API maps to an error
    frame. The lookup fails only for the included key, so the top-level read
    proves the path itself works.
    """
    real_effective = PromptTemplateRepository.effective

    async def broken_effective(
        self: PromptTemplateRepository, prompt_key: str, novel_id: UUID | None
    ) -> PromptTemplate | None:
        if prompt_key == "toy.frame":
            raise OSError("db down")
        return await real_effective(self, prompt_key, novel_id)

    monkeypatch.setattr(PromptTemplateRepository, "effective", broken_effective)

    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("toy.ask", "A[{% include 'toy.frame' %}]", None)
        await session.commit()
        with pytest.raises(OSError, match="db down"):
            await render(session, OWNER, "toy.ask", {})


@pytest.mark.usefixtures("two_users", "toy_registry")
async def test_cancellation_waits_for_the_render_to_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancelled request cannot strand an include read on a torn-down session.

    The render's wait does not abandon its worker: the cancellation surfaces
    only after the render — its include reads included — has finished, so no
    read is scheduled against a session the request already closed. The gate
    holds the include read until the cancellation is in flight; without the
    wait, the task unwinds before the read completes and ``completed`` stops
    at the top-level key.
    """
    real_effective = PromptTemplateRepository.effective
    started = asyncio.Event()
    release = asyncio.Event()
    completed: list[str] = []

    async def gated_effective(
        self: PromptTemplateRepository, prompt_key: str, novel_id: UUID | None
    ) -> PromptTemplate | None:
        if prompt_key == "toy.frame" and not started.is_set():
            started.set()
            await release.wait()
        row = await real_effective(self, prompt_key, novel_id)
        completed.append(prompt_key)
        return row

    monkeypatch.setattr(PromptTemplateRepository, "effective", gated_effective)

    async with Session() as session:
        repo = PromptTemplateRepository(session, OWNER)
        await repo.save("toy.ask", "A[{% include 'toy.frame' %}]", None)
        await repo.save("toy.frame", "FRAME", None)
        await session.commit()

        task = asyncio.create_task(render(session, OWNER, "toy.ask", {}))
        await started.wait()
        task.cancel()
        await asyncio.sleep(0)  # let the cancellation reach the render's wait
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()
        # the include read completed on the live session before the unwind
        assert completed == ["toy.ask", "toy.frame"]
