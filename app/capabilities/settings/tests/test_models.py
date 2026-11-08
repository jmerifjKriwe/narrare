"""The model surface: CRUD, the provider gate, defaults, assignments, the probe.

A model belongs to a provider of the same user, and that is what these tests
pin first: a ``provider_id`` that is nobody's or another user's is refused
with the field — never silently linked. What follows from the provider
carrying the key: the model's reads carry no key material at all, the
connection test authenticates with the provider's key and audits under
``settings.test`` naming the model, and a key its tier can no longer produce
fails the test by naming the provider. The default guard, the cascade, the
window gate and the assignments round out the surface.
"""

import asyncio
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.api.main import app
from app.capabilities.settings.models_service import (
    DefaultProfileRaceError,
    ModelService,
)
from app.capabilities.settings.schemas import ModelCreate, ModelUpdate
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.models import ProviderProfile
from app.kernel.llm.repositories import ProfileRepository, ProviderRepository
from app.kernel.testing.vendor import chat_vendor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.timeout(30)

SECRET = "sk-test-secret"

OTHER = uuid4()


@pytest.fixture(autouse=True)
def fernet_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Fernet tier: every test stores keys as ciphertext, never a keychain."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())


@pytest.fixture
def make_client() -> Callable[[], AsyncClient]:
    """A client factory over the real application, the one home of the transport.

    The race tests need two requests that do not share one connection, so
    they build their own clients here instead of inlining the construction —
    a transport change has exactly one place to land.
    """

    def make() -> AsyncClient:
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return make


@pytest.fixture
async def client(make_client: Callable[[], AsyncClient]) -> AsyncIterator[AsyncClient]:
    """An HTTP client that drives the real application through ASGI."""
    async with make_client() as client:
        yield client


async def test_models_live_at_their_own_path(client: AsyncClient) -> None:
    """The model resource is named for what it holds; the old path is gone."""
    assert (await client.get("/api/settings/models")).status_code == 200
    assert (await client.get("/api/settings/profiles")).status_code == 404


async def _create_provider(
    client: AsyncClient, name: str = "Vendor", **overrides: object
) -> dict[str, object]:
    """Create one local openai-chat provider through the API, requiring the 201."""
    payload: dict[str, object] = {
        "name": name,
        "kind": "openai-chat",
        "base_url": "http://127.0.0.1:9/v1",
        "api_key": SECRET,
    }
    payload.update(overrides)
    response = await client.post("/api/settings/providers", json=payload)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _create(
    client: AsyncClient,
    provider_id: str,
    name: str = "Lokal",
    **overrides: object,
) -> dict[str, object]:
    """Create one model under a provider through the API, requiring the 201."""
    payload: dict[str, object] = {
        "name": name,
        "provider_id": provider_id,
        "model": "vendor-mini",
    }
    payload.update(overrides)
    response = await client.post("/api/settings/models", json=payload)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _stored(model_id: UUID, *columns: str) -> tuple[object, ...]:
    """The model's stored columns, fresh from the table."""
    async with Session() as session:
        profile = await session.get(ProviderProfile, model_id)
    assert profile is not None
    return tuple(getattr(profile, column) for column in columns)


async def test_a_model_names_a_provider_of_the_same_user(client: AsyncClient) -> None:
    """A provider_id nobody carries is refused with the field, never linked."""
    nobody = await client.post(
        "/api/settings/models",
        json={
            "name": "Ohne Anbieter",
            "provider_id": "00000000-0000-0000-0000-000000000099",
            "model": "vendor-mini",
        },
    )
    assert nobody.status_code == 422
    assert "provider_id" in nobody.text

    empty_model = await client.post(
        "/api/settings/models",
        json={"name": "Ohne Modell", "provider_id": str(uuid4()), "model": ""},
    )
    assert empty_model.status_code == 422
    assert "model" in empty_model.text

    # Nothing unusable was stored.
    assert (await client.get("/api/settings/models")).json() == []


async def test_a_model_cannot_point_at_another_users_provider(client: AsyncClient) -> None:
    """The gate is user-scoped: the FK alone would not refuse a cross-user pointer."""
    await seed_user(OTHER)
    async with Session() as session:
        theirs = await ProviderRepository(session, OTHER).create(
            name="Their vendor", kind="openai-chat", base_url="http://127.0.0.1:9/v1"
        )
        await session.commit()

    response = await client.post(
        "/api/settings/models",
        json={"name": "Fremd", "provider_id": str(theirs.id), "model": "vendor-mini"},
    )
    assert response.status_code == 422
    assert "provider_id" in response.text
    assert (await client.get("/api/settings/models")).json() == []

    # The same id is invisible on the provider surface too: another
    # user's provider is neither listed nor reachable here.
    listed = (await client.get("/api/settings/providers")).json()
    assert all(provider["id"] != str(theirs.id) for provider in listed)


async def test_a_model_read_carries_no_key_at_all(client: AsyncClient) -> None:
    """The key and its mask live on the provider; no model read shows either."""
    provider = await _create_provider(client)
    created = await _create(client, str(provider["id"]))
    assert created["provider_id"] == provider["id"]
    assert created["provider_name"] == "Vendor"
    assert "api_key" not in created
    assert "api_key_mask" not in created
    assert "kind" not in created

    listed = (await client.get("/api/settings/models")).json()
    assert listed[0]["provider_name"] == "Vendor"
    assert "api_key" not in listed[0]
    assert "api_key_mask" not in listed[0]

    renamed = await client.patch(f"/api/settings/models/{created['id']}", json={"name": "Renamed"})
    assert renamed.status_code == 200
    assert "api_key" not in renamed.json()


async def test_the_first_model_is_the_default_and_the_second_is_not(client: AsyncClient) -> None:
    """Only the first model becomes the default automatically."""
    provider = await _create_provider(client)
    first = await _create(client, str(provider["id"]), "First")
    assert first["is_default"] is True
    second = await _create(client, str(provider["id"]), "Second")
    assert second["is_default"] is False


async def test_a_patch_cannot_clear_the_name_the_provider_or_the_model(client: AsyncClient) -> None:
    """A present null on the identity fields is refused with the field, not a 500."""
    provider = await _create_provider(client)
    model = await _create(client, str(provider["id"]), "Bleibt")

    for field in ("name", "provider_id", "model"):
        response = await client.patch(f"/api/settings/models/{model['id']}", json={field: None})
        assert response.status_code == 422, (field, response.text)
        assert field in response.text

    listed = (await client.get("/api/settings/models")).json()[0]
    assert listed["name"] == "Bleibt"
    assert listed["model"] == "vendor-mini"


async def test_setting_a_new_default_flips_the_old_one(client: AsyncClient) -> None:
    """Patching ``is_default: true`` unsets the old default in the same transaction."""
    provider = await _create_provider(client)
    first = await _create(client, str(provider["id"]), "First")
    second = await _create(client, str(provider["id"]), "Second")
    response = await client.patch(f"/api/settings/models/{second['id']}", json={"is_default": True})
    assert response.status_code == 200
    assert response.json()["is_default"] is True

    listed = (await client.get("/api/settings/models")).json()
    by_default = {str(model["id"]): model["is_default"] for model in listed}
    assert by_default[str(first["id"])] is False
    assert by_default[str(second["id"])] is True


async def test_two_concurrent_creates_keep_one_default_and_a_named_loser(
    client: AsyncClient,
    make_client: Callable[[], AsyncClient],
) -> None:
    """Two first-models at once: one default survives, never a 500.

    Both requests can read an empty table and both raise their model to the
    default; the partial unique index then refuses the later insert and the
    service maps it to ``DefaultProfileRaceError`` — the router's 409, whose
    row is rolled back with its insert. When the transport serializes the two
    requests instead, the second reads the first's default and creates a
    non-default model: both 201. Either outcome is legal — two defaults are
    not. The frozen-window test below pins the 409 deterministically; this one
    must not insist on an interleaving it cannot force (it flaked at ~1 in 20
    under CI load before the split).
    """
    provider = await _create_provider(client)
    payload: dict[str, object] = {
        "name": "Race",
        "provider_id": provider["id"],
        "model": "vendor-mini",
    }
    # The race needs two requests that do not share one connection: two
    # clients of their own, from the module's one factory.
    async with make_client() as first, make_client() as second:
        responses = await asyncio.gather(
            first.post("/api/settings/models", json=payload),
            second.post("/api/settings/models", json=payload | {"name": "Race two"}),
        )

    statuses = sorted(response.status_code for response in responses)
    assert statuses in ([201, 201], [201, 409]), [response.text for response in responses]
    refused = [response for response in responses if response.status_code == 409]
    if refused:
        assert "default" in refused[0].json()["detail"].lower()

    created = [response for response in responses if response.status_code == 201]
    async with Session() as session:
        rows = await session.scalar(text("SELECT count(*) FROM provider_profiles"))
        defaults = await session.scalar(
            text("SELECT count(*) FROM provider_profiles WHERE is_default")
        )
    assert defaults == 1
    assert rows == len(created)


async def test_a_stale_first_model_read_loses_the_create_as_a_named_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The create guard: a create that read an empty table before a sibling's
    commit collides on the partial index and is the named race, not a 500.

    Real ASGI requests serialize too narrowly to hit this window on demand, so
    the read is held: the left session keeps the empty list it read, the right
    session completes its create, then the left flush of ``is_default = true``
    meets the new holder. Its row is rolled back with the insert.
    """
    left_snapshot = asyncio.Event()
    sibling_done = asyncio.Event()
    left_sessions: list[AsyncSession] = []
    original_ordered = ProfileRepository.ordered

    async def held_ordered(self: ProfileRepository) -> Sequence[ProviderProfile]:
        if left_sessions and self.session is left_sessions[0]:
            left_snapshot.set()
            await sibling_done.wait()
            return ()
        await left_snapshot.wait()
        return await original_ordered(self)

    monkeypatch.setattr(ProfileRepository, "ordered", held_ordered)

    async with Session() as session:
        provider = await ProviderRepository(session, LOCAL_USER_ID).create(
            name="Vendor", kind="openai-chat", base_url="http://127.0.0.1:9/v1"
        )
        await session.commit()
    payload = ModelCreate(name="Race", provider_id=provider.id, model="vendor-mini")

    async with Session() as left, Session() as right:
        left_sessions.append(left)
        left_service = ModelService(left, LOCAL_USER_ID)
        right_service = ModelService(right, LOCAL_USER_ID)

        async def lose() -> None:
            with pytest.raises(DefaultProfileRaceError):
                await left_service.create(payload)

        async def win() -> None:
            await right_service.create(payload)
            sibling_done.set()

        await asyncio.gather(lose(), win())

    async with Session() as session:
        rows = await session.scalar(text("SELECT count(*) FROM provider_profiles"))
        defaults = await session.scalar(
            text("SELECT count(*) FROM provider_profiles WHERE is_default")
        )
    assert (rows, defaults) == (1, 1)


async def test_two_concurrent_default_swaps_keep_one_default_and_a_named_loser(
    client: AsyncClient,
    make_client: Callable[[], AsyncClient],
) -> None:
    """Two sessions swap the default at once: one default survives, never a 500.

    Both requests unset the old holder before raising their own model. Under
    READ COMMITTED the second unset can still act on the pre-swap row, so both
    flush ``is_default = true`` and the partial unique index refuses the later
    one; the service rolls that transaction back and raises the same
    ``DefaultProfileRaceError`` the create race maps, so the loser is a named
    409. When the transactions serialize instead, both are 200 and the later
    committer is the single holder. Either outcome is legal — two defaults are
    not. Through ASGI's transport the two requests here serialize, so this test
    pins the retry-success branch; the frozen-window test below pins the 409.
    """
    provider = await _create_provider(client)
    await _create(client, str(provider["id"]), "First")
    second = await _create(client, str(provider["id"]), "Second")
    third = await _create(client, str(provider["id"]), "Third")

    # The race needs two requests that do not share one connection: two
    # clients of their own, from the module's one factory.
    async with make_client() as left, make_client() as right:
        responses = await asyncio.gather(
            left.patch(f"/api/settings/models/{second['id']}", json={"is_default": True}),
            right.patch(f"/api/settings/models/{third['id']}", json={"is_default": True}),
        )

    statuses = sorted(response.status_code for response in responses)
    assert statuses in ([200, 200], [200, 409]), [response.text for response in responses]
    refused = [response for response in responses if response.status_code == 409]
    if refused:
        assert "default" in refused[0].json()["detail"].lower()

    async with Session() as session:
        defaults = await session.scalar(
            text("SELECT count(*) FROM provider_profiles WHERE is_default")
        )
        holder = await session.scalar(text("SELECT name FROM provider_profiles WHERE is_default"))
    assert defaults == 1
    assert holder in ("Second", "Third")


async def test_a_stale_default_read_loses_the_swap_as_a_named_race(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """The update guard: a swap that read the old holder before a sibling's
    commit collides on the partial index and is the named race, not a 500.

    The window is frozen at the read: the left session keeps the holder list
    it read, the right session completes its swap, then the left flush of
    ``is_default = true`` meets the new holder. Real ASGI requests serialize
    too narrowly to hit this window on demand, so the test holds the read.
    """
    provider = await _create_provider(client)
    await _create(client, str(provider["id"]), "First")
    second = await _create(client, str(provider["id"]), "Second")
    third = await _create(client, str(provider["id"]), "Third")

    left_snapshot = asyncio.Event()
    sibling_done = asyncio.Event()
    left_sessions: list[AsyncSession] = []
    original_ordered = ProfileRepository.ordered

    async def held_ordered(self: ProfileRepository) -> Sequence[ProviderProfile]:
        snapshot = await original_ordered(self)
        if left_sessions and self.session is left_sessions[0]:
            left_snapshot.set()
            await sibling_done.wait()
        else:
            await left_snapshot.wait()
        return snapshot

    monkeypatch.setattr(ProfileRepository, "ordered", held_ordered)

    async with Session() as left, Session() as right:
        left_sessions.append(left)
        left_service = ModelService(left, LOCAL_USER_ID)
        right_service = ModelService(right, LOCAL_USER_ID)

        async def lose() -> None:
            with pytest.raises(DefaultProfileRaceError):
                await left_service.update(UUID(str(second["id"])), ModelUpdate(is_default=True))

        async def win() -> None:
            await right_service.update(UUID(str(third["id"])), ModelUpdate(is_default=True))
            sibling_done.set()

        await asyncio.gather(lose(), win())

    async with Session() as session:
        defaults = await session.scalar(
            text("SELECT count(*) FROM provider_profiles WHERE is_default")
        )
        holder = await session.scalar(text("SELECT name FROM provider_profiles WHERE is_default"))
    assert (defaults, holder) == (1, "Third")


async def test_a_lost_swap_on_patch_is_a_named_409(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """The update route maps the service's race to 409, never a bare 500."""
    provider = await _create_provider(client)
    model = await _create(client, str(provider["id"]))

    async def lost(
        self: ModelService, model_id: UUID, payload: ModelUpdate
    ) -> tuple[object, object]:
        raise DefaultProfileRaceError("another swap made its model the default first")

    monkeypatch.setattr(ModelService, "update", lost)
    response = await client.patch(f"/api/settings/models/{model['id']}", json={"is_default": True})

    assert response.status_code == 409
    assert "default" in response.json()["detail"]


async def test_set_default_flips_the_old_default_out_before_raising_the_new(
    client: AsyncClient,
) -> None:
    """The swap keeps a single default through both flushes, index in force."""
    provider = await _create_provider(client)
    await _create(client, str(provider["id"]), "First")
    second = await _create(client, str(provider["id"]), "Second")

    async with Session() as session:
        await ModelService(session, LOCAL_USER_ID).set_default(UUID(str(second["id"])))

    async with Session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT name, is_default FROM provider_profiles ORDER BY is_default DESC, name"
                )
            )
        ).all()
    assert [(row.name, row.is_default) for row in rows] == [("Second", True), ("First", False)]
    defaults = sum(1 for row in rows if row.is_default)
    assert defaults == 1


async def test_a_model_cannot_be_patched_out_of_being_the_default(client: AsyncClient) -> None:
    """``is_default: false`` would leave the user without one; it is refused."""
    provider = await _create_provider(client)
    model = await _create(client, str(provider["id"]))
    response = await client.patch(f"/api/settings/models/{model['id']}", json={"is_default": False})
    assert response.status_code == 422
    assert "is_default" in response.text


async def test_the_default_model_cannot_be_deleted_and_the_error_names_the_way_out(
    client: AsyncClient,
) -> None:
    """The only-default model's DELETE is a 409 that says how to proceed."""
    provider = await _create_provider(client)
    model = await _create(client, str(provider["id"]))
    response = await client.delete(f"/api/settings/models/{model['id']}")
    assert response.status_code == 409
    assert "second" in response.json()["detail"]
    listed = (await client.get("/api/settings/models")).json()
    assert [str(m["id"]) for m in listed] == [str(model["id"])]


async def test_deleting_a_model_cascades_its_assignments(client: AsyncClient) -> None:
    """A deleted non-default model takes its assignments with it."""
    provider = await _create_provider(client)
    await _create(client, str(provider["id"]), "Default")
    doomed = await _create(client, str(provider["id"]), "Doomed")
    assigned = await client.put(
        "/api/settings/assignments/chat.ask", json={"profile_id": doomed["id"]}
    )
    assert assigned.status_code == 200

    deleted = await client.delete(f"/api/settings/models/{doomed['id']}")
    assert deleted.status_code == 204

    assert (await client.get("/api/settings/assignments")).json() == []


async def test_moving_a_model_to_another_provider_stores_the_new_pointer(
    client: AsyncClient,
) -> None:
    """A provider move repoints the row; the provider owns every endpoint fact."""
    vendor = await _create_provider(client)
    geist = await client.post("/api/settings/providers", json={"name": "Geist", "kind": "fake"})
    assert geist.status_code == 201
    model = await _create(client, str(vendor["id"]))

    moved = await client.patch(
        f"/api/settings/models/{model['id']}",
        json={"provider_id": geist.json()["id"]},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["provider_name"] == "Geist"

    (stored_provider,) = await _stored(UUID(str(model["id"])), "provider_id")
    assert str(stored_provider) == geist.json()["id"]


async def test_a_model_cannot_be_patched_onto_another_users_provider(
    client: AsyncClient,
) -> None:
    """The update path runs the same user-scoped gate the create does."""
    await seed_user(OTHER)
    async with Session() as session:
        theirs = await ProviderRepository(session, OTHER).create(
            name="Their vendor", kind="openai-chat", base_url="http://127.0.0.1:9/v1"
        )
        await session.commit()

    provider = await _create_provider(client)
    model = await _create(client, str(provider["id"]))

    patched = await client.patch(
        f"/api/settings/models/{model['id']}",
        json={"provider_id": str(theirs.id)},
    )
    assert patched.status_code == 422
    assert "provider_id" in patched.text

    # The refusal stored nothing: the model still points at its own provider.
    listed = (await client.get("/api/settings/models")).json()
    assert [str(entry["provider_id"]) for entry in listed] == [str(provider["id"])]


async def test_a_model_whose_provider_is_not_the_users_is_skipped_by_the_list(
    client: AsyncClient,
) -> None:
    """A pointer the user's provider set cannot resolve is skipped, never a 500.

    Unreachable through the writers (the gate refuses a cross-user pointer),
    reachable by repair SQL: the FK has no user scope, so a stored row can
    name a provider that exists but is not the user's. The list skips the
    dangling row and stays readable — the single-row reads are the ones that
    refuse by name (the service's ``_paired``).
    """
    await seed_user(OTHER)
    async with Session() as session:
        theirs = await ProviderRepository(session, OTHER).create(
            name="Their vendor", kind="openai-chat", base_url="http://127.0.0.1:9/v1"
        )
        await session.commit()

    provider = await _create_provider(client)
    doomed = await _create(client, str(provider["id"]), "Dangling")
    async with Session() as session:
        await session.execute(
            text("UPDATE provider_profiles SET provider_id = :theirs WHERE id = :id"),
            {"theirs": str(theirs.id), "id": str(doomed["id"])},
        )
        await session.commit()

    listed = await client.get("/api/settings/models")
    assert listed.status_code == 200
    assert [entry["name"] for entry in listed.json()] == []


async def test_an_output_reservation_that_leaves_no_input_room_is_refused(
    client: AsyncClient,
) -> None:
    """``max_output_tokens`` must stay below ``context_window`` when both are set.

    Equality leaves a zero input budget and greater-than a negative one; the gate
    refuses both where the pair is known, so the allocator only ever sees ordered
    pairs (a catalog-merged degenerate pair is refused there, never clamped, D8).
    The gate runs on the answering kinds only: a fake never allocates, so its
    reversed pair is none of the gate's business — while the second answering
    kind (anthropic) is gated exactly like openai-chat.
    """
    provider = await _create_provider(client)
    fake = await client.post("/api/settings/providers", json={"name": "Geist", "kind": "fake"})
    anthropic = await client.post(
        "/api/settings/providers",
        json={
            "name": "Anthropic",
            "kind": "anthropic",
            "base_url": "https://api.anthropic.com/v1",
            "api_key": SECRET,
        },
    )
    assert anthropic.status_code == 201, anthropic.text
    reversed_on_fake = await client.post(
        "/api/settings/models",
        json={
            "name": "Umgekehrt",
            "provider_id": fake.json()["id"],
            "model": "fake",
            "context_window": 1000,
            "max_output_tokens": 2000,
        },
    )
    assert reversed_on_fake.status_code == 201, reversed_on_fake.text

    reversed_on_anthropic = await client.post(
        "/api/settings/models",
        json={
            "name": "Umgekehrt",
            "provider_id": anthropic.json()["id"],
            "model": "claude-sonnet-4-5",
            "context_window": 1000,
            "max_output_tokens": 2000,
        },
    )
    assert reversed_on_anthropic.status_code == 422
    assert "max_output_tokens" in reversed_on_anthropic.text

    equal = await client.post(
        "/api/settings/models",
        json={
            "name": "Grenze",
            "provider_id": provider["id"],
            "model": "vendor-mini",
            "context_window": 1000,
            "max_output_tokens": 1000,
        },
    )
    assert equal.status_code == 422
    assert "max_output_tokens" in equal.text

    greater = await client.post(
        "/api/settings/models",
        json={
            "name": "Über",
            "provider_id": provider["id"],
            "model": "vendor-mini",
            "context_window": 1000,
            "max_output_tokens": 2000,
        },
    )
    assert greater.status_code == 422
    assert "max_output_tokens" in greater.text

    ordered = await _create(
        client,
        str(provider["id"]),
        "Geordnet",
        context_window=1000,
        max_output_tokens=200,
    )
    assert ordered["context_window"] == 1000

    # Shrinking the window under the stored reservation is the same refusal.
    patched = await client.patch(
        f"/api/settings/models/{ordered['id']}", json={"context_window": 150}
    )
    assert patched.status_code == 422
    assert "max_output_tokens" in patched.text


async def test_the_connection_test_hits_the_provider_and_audits_settings_test(
    client: AsyncClient,
) -> None:
    """One cheap completion through the provider, one ``settings.test`` audit row.

    The request asks for the model's string and authenticates with the
    provider's key — the split the whole cut is about.
    """
    with chat_vendor() as vendor:
        provider = await _create_provider(client, base_url=vendor.base_url)
        model = await _create(client, str(provider["id"]))
        result = await client.post(f"/api/settings/models/{model['id']}/test")

    assert result.status_code == 200
    body = result.json()
    assert body["ok"] is True
    assert body["error"] is None
    assert body["latency_ms"] >= 0

    [request] = vendor.received
    assert request["path"] == "/v1/chat/completions"
    assert request["body"]["model"] == "vendor-mini"
    assert request["headers"]["authorization"] == f"Bearer {SECRET}"

    async with Session() as session:
        row = (
            await session.execute(
                text(
                    "SELECT task_key, provider_kind, model, profile_id, status, cost_usd"
                    " FROM llm_calls"
                )
            )
        ).one()
    assert row.task_key == "settings.test"
    assert (row.provider_kind, row.model, row.status) == ("openai-chat", "vendor-mini", "ok")
    assert str(row.profile_id) == str(model["id"])
    assert row.cost_usd == 0.0  # the vendor is local: free, not unknown


async def test_a_failing_connection_test_reports_the_failure_and_audits_it(
    client: AsyncClient,
) -> None:
    """A vendor refusal is a failed test result, not a failed HTTP request."""
    with chat_vendor() as vendor:
        vendor.refuse_requests()
        provider = await _create_provider(client, base_url=vendor.base_url)
        model = await _create(client, str(provider["id"]))
        result = await client.post(f"/api/settings/models/{model['id']}/test")

    assert result.status_code == 200
    body = result.json()
    assert body["ok"] is False
    assert body["error"] is not None

    async with Session() as session:
        row = (await session.execute(text("SELECT status, error FROM llm_calls"))).one()
    assert row.status == "error"
    assert row.error is not None


async def test_a_model_whose_provider_key_is_lost_fails_the_test_by_name(
    client: AsyncClient,
) -> None:
    """Undecryptable ciphertext on the provider is a failed test naming it."""
    provider = await _create_provider(client)
    model = await _create(client, str(provider["id"]))
    async with Session() as session:
        await session.execute(
            text("UPDATE llm_providers SET api_key = 'gAAAAA-not-ciphertext' WHERE id = :id"),
            {"id": provider["id"]},
        )
        await session.commit()

    result = await client.post(f"/api/settings/models/{model['id']}/test")

    assert result.status_code == 200
    body = result.json()
    assert body["ok"] is False
    assert str(provider["id"]) in body["error"]


async def test_assignments_accept_unknown_forward_compatible_task_keys(client: AsyncClient) -> None:
    """Any non-empty task key can be assigned and cleared, listed or not."""
    provider = await _create_provider(client)
    model = await _create(client, str(provider["id"]))
    assigned = await client.put(
        "/api/settings/assignments/brandnew.task", json={"profile_id": model["id"]}
    )
    assert assigned.status_code == 200
    assert assigned.json() == {
        "task_key": "brandnew.task",
        "profile_id": model["id"],
    }

    listed = (await client.get("/api/settings/assignments")).json()
    assert listed == [{"task_key": "brandnew.task", "profile_id": model["id"]}]

    cleared = await client.put("/api/settings/assignments/brandnew.task", json={"profile_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["profile_id"] is None
    assert (await client.get("/api/settings/assignments")).json() == []


async def test_an_assignment_for_a_missing_model_is_refused(client: AsyncClient) -> None:
    """Assigning a task to a model that is not the user's is a 404."""
    response = await client.put(
        "/api/settings/assignments/chat.ask",
        json={"profile_id": "00000000-0000-0000-0000-000000000099"},
    )
    assert response.status_code == 404


async def test_a_missing_model_is_a_404_on_every_named_route(client: AsyncClient) -> None:
    """Patch, delete and test all name the missing model the same way."""
    missing = "00000000-0000-0000-0000-000000000099"
    for method, path in (
        ("PATCH", f"/api/settings/models/{missing}"),
        ("DELETE", f"/api/settings/models/{missing}"),
        ("POST", f"/api/settings/models/{missing}/test"),
    ):
        response = await client.request(method, path, json={} if method == "PATCH" else None)
        assert response.status_code == 404, (method, response.text)
