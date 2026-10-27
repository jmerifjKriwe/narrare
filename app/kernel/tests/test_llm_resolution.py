"""The resolution cascade: which provider serves one task for one user.

Five tiers, first hit wins: the task's own assignment, an assignment standing
in for the task's capability segment, the user's default profile, the
environment (``NARRE_LLM_PROVIDER``, semantics unchanged), the fake. The
resolved structure is also the audit's fact sheet — kind, model, profile id,
and the numeric tunables the profile stored or the catalog knows — so the
per-call row names the configuration that served it, and a profile whose key
its tier can no longer produce refuses by name before any call runs.
"""

from collections.abc import AsyncIterator  # noqa: TC003
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm import catalog
from app.kernel.llm.audit import audited_stream
from app.kernel.llm.catalog import ModelInfo
from app.kernel.llm.contract import DONE, CompletionEvent, CompletionRequest, Delta, Usage
from app.kernel.llm.fake import FakeProvider
from app.kernel.llm.models import ProviderProfile  # noqa: TC001  the helper's return annotation
from app.kernel.llm.openai_chat import OpenAIChatProvider
from app.kernel.llm.profiles import AssignmentRepository, ProfileRepository
from app.kernel.llm.resolution import (
    KNOWN_TASK_KEYS,
    ResolvedProvider,
    environment_provider,
    resolve_provider,
)
from app.kernel.secrets import KeyUnavailableError, save_key

OWNER = uuid4()
OTHER = uuid4()
REMOTE = "https://api.vendor.example/v1"

ACME = ModelInfo(
    context_window=100_000,
    max_output_tokens=4_096,
    input_price_per_mtok=3.0,
    output_price_per_mtok=15.0,
    supports_json_schema=True,
    supports_tools=True,
    supports_vision=False,
)


@pytest.fixture
async def two_users(empty_tables: None, schema: None) -> None:
    """Two seeded users: one owns the rows, the other proves the isolation."""
    await seed_user(OWNER)
    await seed_user(OTHER)


async def _fake_profile(
    session: AsyncSession,
    user_id: UUID,
    *,
    name: str,
    model: str | None = None,
    is_default: bool = False,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    request_timeout: float | None = None,
) -> ProviderProfile:
    """One fake profile of the user's, through the repository, uncommitted."""
    return await ProfileRepository(session, user_id).create(
        name=name,
        kind="fake",
        model=model,
        is_default=is_default,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        request_timeout=request_timeout,
    )


async def _resolve(user_id: UUID, task_key: str) -> ResolvedProvider:
    """Resolve on a session of the test's own, the way every caller does."""
    async with Session() as session:
        return await resolve_provider(session, user_id, task_key)


def test_the_known_task_keys_are_the_five_capability_tasks() -> None:
    """Verify the constant Task 4 validates assignments against."""
    assert KNOWN_TASK_KEYS == (
        "writing.continuation",
        "chat.ask",
        "knowledge.extract-entities",
        "knowledge.check-consistency",
        "settings.test",
    )


@pytest.mark.usefixtures("two_users")
async def test_exact_beats_prefix_beats_default() -> None:
    """The task's own assignment wins, then the segment's, then the default."""
    async with Session() as session:
        default = await _fake_profile(
            session, OWNER, name="Default", model="default-model", is_default=True
        )
        prefix = await _fake_profile(session, OWNER, name="Prefix", model="prefix-model")
        exact = await _fake_profile(session, OWNER, name="Exact", model="exact-model")
        assignments = AssignmentRepository(session, OWNER)
        # A sibling task's assignment stands in for the whole writing segment.
        await assignments.set("writing.revision", prefix.id)
        await assignments.set("writing.continuation", exact.id)
        await session.commit()

    resolved = await _resolve(OWNER, "writing.continuation")
    assert (resolved.profile_id, resolved.model) == (exact.id, "exact-model")

    async with Session() as session:
        await AssignmentRepository(session, OWNER).clear("writing.continuation")
        await session.commit()
    resolved = await _resolve(OWNER, "writing.continuation")
    assert (resolved.profile_id, resolved.model) == (prefix.id, "prefix-model")

    async with Session() as session:
        await AssignmentRepository(session, OWNER).clear("writing.revision")
        await session.commit()
    resolved = await _resolve(OWNER, "writing.continuation")
    assert (resolved.profile_id, resolved.model) == (default.id, "default-model")


@pytest.mark.usefixtures("two_users")
async def test_the_bare_key_and_other_segments_never_stand_in() -> None:
    """An assignment on ``writing`` itself or on ``chat.ask`` serves no writing task."""
    async with Session() as session:
        default = await _fake_profile(
            session, OWNER, name="Default", model="default-model", is_default=True
        )
        elsewhere = await _fake_profile(session, OWNER, name="Elsewhere", model="other-model")
        assignments = AssignmentRepository(session, OWNER)
        await assignments.set("writing", elsewhere.id)  # the bare key: for_task's own
        await assignments.set("chat.ask", elsewhere.id)  # another capability's segment
        await session.commit()

    resolved = await _resolve(OWNER, "writing.continuation")
    assert (resolved.profile_id, resolved.model) == (default.id, "default-model")


@pytest.mark.usefixtures("two_users")
async def test_a_deleted_profiles_assignment_falls_back_to_the_default() -> None:
    """Deleting an assigned non-default profile drops its tasks down the cascade."""
    async with Session() as session:
        default = await _fake_profile(
            session, OWNER, name="Default", model="default-model", is_default=True
        )
        doomed = await _fake_profile(session, OWNER, name="Doomed", model="doomed-model")
        assignments = AssignmentRepository(session, OWNER)
        await assignments.set("chat.ask", doomed.id)
        await session.commit()
        # The database cascades the assignment with the profile (Task 1's
        # pin); the resolver must then fall through without a sound.
        await ProfileRepository(session, OWNER).delete(doomed)
        await session.commit()

    resolved = await _resolve(OWNER, "chat.ask")
    assert (resolved.profile_id, resolved.model) == (default.id, "default-model")


@pytest.mark.usefixtures("empty_tables")
async def test_without_profiles_the_environment_tier_serves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``openai-compatible`` resolves as the alias it is: kind openai-chat, env facts."""
    monkeypatch.setenv("NARRE_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("NARRE_LLM_MODEL", "acme/turbo-3")
    monkeypatch.setenv("NARRE_LLM_BASE_URL", REMOTE)
    monkeypatch.setenv("NARRE_LLM_API_KEY", "sk-env")

    resolved = await _resolve(OWNER, "chat.ask")

    assert resolved.profile_id is None
    # The alias names the adapter; the audit's kind column records the kind.
    assert resolved.kind == "openai-chat"
    assert resolved.model == "acme/turbo-3"
    assert resolved.base_url == REMOTE
    assert resolved.api_key == "sk-env"
    assert isinstance(resolved.provider, OpenAIChatProvider)


@pytest.mark.usefixtures("empty_tables")
async def test_without_profiles_and_environment_the_fake_serves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No profiles and no NARRE_LLM_PROVIDER: the fake keeps a fresh clone answering."""
    monkeypatch.delenv("NARRE_LLM_PROVIDER", raising=False)

    resolved = await _resolve(OWNER, "writing.continuation")

    assert isinstance(resolved.provider, FakeProvider)
    assert resolved.profile_id is None
    assert (resolved.kind, resolved.model) == ("fake", "fake")
    assert (resolved.context_window, resolved.max_output_tokens) == (None, None)
    assert (resolved.temperature, resolved.request_timeout) == (None, None)
    assert resolved.base_url is None
    assert resolved.api_key is None


@pytest.mark.usefixtures("empty_tables")
def test_an_unknown_environment_name_refuses_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mistyped NARRE_LLM_PROVIDER refuses by name, as the process-wide choice did."""
    monkeypatch.setenv("NARRE_LLM_PROVIDER", "nonsense")
    with pytest.raises(RuntimeError, match="unknown LLM provider"):
        environment_provider()


@pytest.mark.usefixtures("two_users")
async def test_two_users_with_different_defaults_resolve_to_their_own() -> None:
    """Per-user isolation: each user's default serves their tasks, never the other's."""
    async with Session() as session:
        mine = await _fake_profile(
            session, OWNER, name="Owner's", model="owner-model", is_default=True
        )
        theirs = await _fake_profile(
            session, OTHER, name="Other's", model="other-model", is_default=True
        )
        await session.commit()

    owner_resolved = await _resolve(OWNER, "chat.ask")
    other_resolved = await _resolve(OTHER, "chat.ask")
    assert (owner_resolved.profile_id, owner_resolved.model) == (mine.id, "owner-model")
    assert (other_resolved.profile_id, other_resolved.model) == (theirs.id, "other-model")


@pytest.mark.usefixtures("two_users")
async def test_a_fake_profile_carries_its_model_through() -> None:
    """A fake profile's model is free text: ignored for answering, carried to the facts."""
    async with Session() as session:
        profile = await _fake_profile(
            session, OWNER, name="Ghost", model="ghost-writer", is_default=True
        )
        await session.commit()

    resolved = await _resolve(OWNER, "writing.continuation")
    assert isinstance(resolved.provider, FakeProvider)
    assert resolved.kind == "fake"
    assert resolved.model == "ghost-writer"
    assert resolved.profile_id == profile.id


@pytest.mark.usefixtures("two_users")
async def test_an_openai_chat_profile_resolves_its_endpoint_and_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The profile's endpoint serves, and its key loads from the tier that stored it."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())
    async with Session() as session:
        profiles = ProfileRepository(session, OWNER)
        profile = await profiles.create(
            name="Hosted", kind="openai-chat", base_url=REMOTE, model="acme/turbo-3"
        )
        await profiles.update(profile, api_key=save_key(profile.id, "sk-profile"))
        await session.commit()

    resolved = await _resolve(OWNER, "chat.ask")
    assert resolved.profile_id == profile.id
    assert (resolved.kind, resolved.model, resolved.base_url) == (
        "openai-chat",
        "acme/turbo-3",
        REMOTE,
    )
    assert resolved.api_key == "sk-profile"
    assert isinstance(resolved.provider, OpenAIChatProvider)


@pytest.mark.usefixtures("two_users")
async def test_a_local_openai_chat_profile_without_a_key_resolves_keyless() -> None:
    """The settings gate allows a local endpoint without a key; none is loaded.

    An empty ``api_key`` column normally names the keyring tier; without a
    hint there was never a key at all, and a local endpoint does not need
    one — the adapter sends no Authorization header without a key.
    """
    async with Session() as session:
        await ProfileRepository(session, OWNER).create(
            name="Lokal",
            kind="openai-chat",
            base_url="http://127.0.0.1:11434/v1",
            model="llama3",
        )
        await session.commit()

    resolved = await _resolve(OWNER, "chat.ask")
    assert isinstance(resolved.provider, OpenAIChatProvider)
    # No key was ever stored: the resolved carrier says "no key" (None), the
    # same absence the fake tier reports, and the adapter sends no header.
    assert (resolved.base_url, resolved.api_key) == ("http://127.0.0.1:11434/v1", None)


@pytest.mark.usefixtures("two_users")
async def test_a_profile_whose_key_is_lost_refuses_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KeyUnavailableError propagates out of resolution, naming the profile id."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())
    async with Session() as session:
        profile = await ProfileRepository(session, OWNER).create(
            name="Broken",
            kind="openai-chat",
            base_url=REMOTE,
            model="acme/turbo-3",
            # Ciphertext another NARRE_SECRET_KEY made: undecryptable on purpose.
            api_key="gAAAAABlindtext-not-what-this-key-encrypted",
        )
        await session.commit()

    with pytest.raises(KeyUnavailableError, match=str(profile.id)):
        await _resolve(OWNER, "chat.ask")


@pytest.mark.usefixtures("two_users")
async def test_the_resolver_merges_the_catalogs_tunables_with_the_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The profile's columns win; the catalog's fill the unset; unknown stays None."""
    monkeypatch.setattr(catalog, "load_catalog", lambda: {"acme/turbo-3": ACME})
    async with Session() as session:
        await _fake_profile(
            session, OWNER, name="Catalogued", model="acme/turbo-3", is_default=True
        )
        pinned = await _fake_profile(
            session,
            OWNER,
            name="Pinned",
            model="acme/turbo-3",
            context_window=8_192,
            max_output_tokens=512,
            temperature=0.7,
            request_timeout=30.0,
        )
        unknown = await _fake_profile(session, OWNER, name="Unknown", model="no-catalog-entry")
        assignments = AssignmentRepository(session, OWNER)
        await assignments.set("chat.ask", pinned.id)
        await assignments.set("knowledge.check-consistency", unknown.id)
        await session.commit()

    catalogued = await _resolve(OWNER, "writing.continuation")
    assert (catalogued.context_window, catalogued.max_output_tokens) == (100_000, 4_096)
    assert (catalogued.temperature, catalogued.request_timeout) == (None, None)

    pinned_resolved = await _resolve(OWNER, "chat.ask")
    assert (pinned_resolved.context_window, pinned_resolved.max_output_tokens) == (8_192, 512)
    assert (pinned_resolved.temperature, pinned_resolved.request_timeout) == (0.7, 30.0)

    unknown_resolved = await _resolve(OWNER, "knowledge.check-consistency")
    assert (unknown_resolved.context_window, unknown_resolved.max_output_tokens) == (None, None)


@pytest.mark.usefixtures("two_users")
async def test_stored_tunables_survive_an_uncatalogued_model() -> None:
    """Merge edge: on a model no tier reaches, the profile's stored values stand.

    The catalog contributes nothing here, so the stored columns are the only
    source — a profile whose numbers came from its user keeps them instead of
    collapsing to NULL with the unknown model.
    """
    async with Session() as session:
        pinned = await _fake_profile(
            session,
            OWNER,
            name="Pinned-unknown",
            model="no-catalog-entry-for-this-test",
            context_window=8_192,
            max_output_tokens=256,
        )
        await session.commit()

    resolved = await _resolve(OWNER, "chat.ask")
    assert resolved.profile_id == pinned.id
    assert (resolved.context_window, resolved.max_output_tokens) == (8_192, 256)


@pytest.mark.usefixtures("two_users")
async def test_an_unknown_task_key_resolves_through_the_cascade() -> None:
    """Forward compatibility: a task key nobody lists still resolves."""
    async with Session() as session:
        default = await _fake_profile(
            session, OWNER, name="Default", model="default-model", is_default=True
        )
        await session.commit()

    resolved = await _resolve(OWNER, "brandnew.task")
    assert (resolved.profile_id, resolved.model) == (default.id, "default-model")


class _ScriptedProvider:
    """A provider with one scripted answer, so the audit's facts are the test's."""

    def __init__(self, events: tuple[CompletionEvent, ...]) -> None:
        """Store the events to yield."""
        self.events = events

    def describe(self) -> str:
        """Identify this scripted stand-in."""
        return "scripted"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Yield every scripted event."""
        for event in self.events:
            yield event


@pytest.mark.usefixtures("two_users")
async def test_audited_stream_records_the_resolved_facts_and_the_computed_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The row names the resolved kind, model and profile, priced by the catalog."""
    monkeypatch.setattr(catalog, "load_catalog", lambda: {"acme/turbo-3": ACME})
    profile_id = uuid4()
    resolved = ResolvedProvider(
        provider=_ScriptedProvider(
            (Delta(text="part "), Usage(input_tokens=1_000, output_tokens=2_000), DONE)
        ),
        profile_id=profile_id,
        kind="openai-chat",
        model="acme/turbo-3",
        context_window=None,
        max_output_tokens=None,
        temperature=None,
        request_timeout=None,
        base_url=REMOTE,
        api_key="sk-never-in-any-row",
    )

    events = [
        event
        async for event in audited_stream(
            resolved, CompletionRequest.user("Continue"), user_id=OWNER, task_key="chat.ask"
        )
    ]
    assert events[-1] is DONE

    async with Session() as session:
        row = (
            await session.execute(
                text("SELECT provider_kind, model, profile_id, cost_usd FROM llm_calls")
            )
        ).one()
    assert (row.provider_kind, row.model, row.profile_id) == (
        "openai-chat",
        "acme/turbo-3",
        profile_id,
    )
    # 1 000 * 3.0 + 2 000 * 15.0 per million tokens, the resolved facts' price.
    assert row.cost_usd == pytest.approx(0.033)
