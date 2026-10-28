"""The provider-profile surface: CRUD, masked keys, defaults, assignments, probes.

The API key is the one secret the settings hold; everything these tests pin
follows from that: the full key appears in exactly one response (the create),
every later read shows the mask, the stored column is ciphertext, and a key
its tier can no longer produce fails by naming the profile — never the key.
The default guard, the cascade, the half-configuration refusals and the two
probes (test, discovery) run against the stand-in chat vendor over real HTTP.
"""

import asyncio
from collections.abc import Sequence  # noqa: TC003
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from keyring.errors import KeyringError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.api.main import app
from app.capabilities.settings.profiles_service import (
    DefaultProfileRaceError,
    ProfileService,
)
from app.capabilities.settings.schemas import ProfileCreate, ProfileUpdate
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.llm.models import ProviderProfile
from app.kernel.llm.profiles import ProfileRepository
from app.kernel.testing.vendor import chat_vendor

pytestmark = pytest.mark.timeout(30)

SECRET = "sk-test-secret"
REMOTE = "https://api.vendor.example/v1"


@pytest.fixture(autouse=True)
def fernet_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Fernet tier: every test stores keys as ciphertext, never a keychain."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())


def _client() -> AsyncClient:
    """An HTTP client that drives the real application through ASGI."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create(
    client: AsyncClient, name: str = "Lokal", **overrides: object
) -> dict[str, object]:
    """Create one local openai-chat profile through the API, requiring the 201."""
    payload: dict[str, object] = {
        "name": name,
        "kind": "openai-chat",
        "base_url": "http://127.0.0.1:9/v1",
        "model": "vendor-mini",
        "api_key": SECRET,
    }
    payload.update(overrides)
    response = await client.post("/api/settings/profiles", json=payload)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _stored(profile_id: UUID, *columns: str) -> tuple[object, ...]:
    """The profile's stored columns, fresh from the table."""
    async with Session() as session:
        profile = await session.get(ProviderProfile, profile_id)
    assert profile is not None
    return tuple(getattr(profile, column) for column in columns)


async def test_create_returns_the_full_key_once_and_masks_every_read_after() -> None:
    """The one full-key response is the create; every later read shows the mask."""
    async with _client() as client:
        created = await _create(client)
        profile_id = UUID(str(created["id"]))
        assert created["api_key"] == SECRET  # exactly once, here
        assert created["api_key_mask"] == "sk-…cret"
        assert created["is_default"] is True  # the first profile is the default

        listed = (await client.get("/api/settings/profiles")).json()
        assert listed[0]["api_key_mask"] == "sk-…cret"
        assert "api_key" not in listed[0]

        renamed = await client.patch(
            f"/api/settings/profiles/{profile_id}", json={"name": "Renamed"}
        )
        assert renamed.status_code == 200
        assert renamed.json()["api_key_mask"] == "sk-…cret"
        assert "api_key" not in renamed.json()

    # The stored column is ciphertext: the plaintext never touches the table.
    (column, hint) = await _stored(profile_id, "api_key", "api_key_hint")
    assert column != SECRET
    assert SECRET not in str(column)
    assert hint == "cret"


async def test_the_second_profile_is_not_the_default() -> None:
    """Only the first profile becomes the default automatically."""
    async with _client() as client:
        await _create(client, "First")
        second = await _create(client, "Second")
        assert second["is_default"] is False


async def test_update_with_an_empty_key_keeps_the_stored_one() -> None:
    """An empty ``api_key`` in an update means "keep the stored key", not "clear"."""
    async with _client() as client:
        profile = await _create(client)
        profile_id = UUID(str(profile["id"]))
        before = await _stored(profile_id, "api_key")

        for payload in ({"name": "Umbenannt"}, {"api_key": ""}, {"api_key": None}):
            response = await client.patch(
                f"/api/settings/profiles/{profile_id}",
                json=payload,
            )
            assert response.status_code == 200, response.text
            assert response.json()["api_key_mask"] == "sk-…cret"

    assert await _stored(profile_id, "api_key") == before


async def test_setting_a_new_default_flips_the_old_one() -> None:
    """Patching ``is_default: true`` unsets the old default in the same transaction."""
    async with _client() as client:
        first = await _create(client, "First")
        second = await _create(client, "Second")
        response = await client.patch(
            f"/api/settings/profiles/{second['id']}", json={"is_default": True}
        )
        assert response.status_code == 200
        assert response.json()["is_default"] is True

        listed = (await client.get("/api/settings/profiles")).json()
        by_default = {str(profile["id"]): profile["is_default"] for profile in listed}
        assert by_default[str(first["id"])] is False
        assert by_default[str(second["id"])] is True


async def test_two_concurrent_creates_keep_one_default_and_a_named_loser() -> None:
    """Two first-profiles at once: one default survives, never a 500.

    Both requests can read an empty table and both raise their profile to the
    default; the partial unique index then refuses the later insert and the
    service maps it to ``DefaultProfileRaceError`` — the router's 409, whose
    row is rolled back with its insert. When the transport serializes the two
    requests instead, the second reads the first's default and creates a
    non-default profile: both 201. Either outcome is legal — two defaults are
    not. The frozen-window test below pins the 409 deterministically; this one
    must not insist on an interleaving it cannot force (it flaked at ~1 in 20
    under CI load before the split).
    """
    payload: dict[str, object] = {
        "name": "Race",
        "kind": "openai-chat",
        "base_url": REMOTE,
        "model": "vendor-mini",
        "api_key": SECRET,
    }
    async with _client() as first, _client() as second:
        responses = await asyncio.gather(
            first.post("/api/settings/profiles", json=payload),
            second.post("/api/settings/profiles", json=payload | {"name": "Race two"}),
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


async def test_a_stale_first_profile_read_loses_the_create_as_a_named_race(
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

    payload = ProfileCreate(
        name="Race", kind="openai-chat", base_url=REMOTE, model="vendor-mini", api_key=SECRET
    )

    async with Session() as left, Session() as right:
        left_sessions.append(left)
        left_service = ProfileService(left, LOCAL_USER_ID)
        right_service = ProfileService(right, LOCAL_USER_ID)

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


async def test_two_concurrent_default_swaps_keep_one_default_and_a_named_loser() -> None:
    """Two sessions swap the default at once: one default survives, never a 500.

    Both requests unset the old holder before raising their own profile. Under
    READ COMMITTED the second unset can still act on the pre-swap row, so both
    flush ``is_default = true`` and the partial unique index refuses the later
    one; the service rolls that transaction back and raises the same
    ``DefaultProfileRaceError`` the create race maps, so the loser is a named
    409. When the transactions serialize instead, both are 200 and the later
    committer is the single holder. Either outcome is legal — two defaults are
    not. Through ASGI's transport the two requests here serialize, so this test
    pins the retry-success branch; the frozen-window test below pins the 409.
    """
    async with _client() as client:
        await _create(client, "First")
        second = await _create(client, "Second")
        third = await _create(client, "Third")

    async with _client() as left, _client() as right:
        responses = await asyncio.gather(
            left.patch(f"/api/settings/profiles/{second['id']}", json={"is_default": True}),
            right.patch(f"/api/settings/profiles/{third['id']}", json={"is_default": True}),
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The update guard: a swap that read the old holder before a sibling's
    commit collides on the partial index and is the named race, not a 500.

    The window is frozen at the read: the left session keeps the holder list
    it read, the right session completes its swap, then the left flush of
    ``is_default = true`` meets the new holder. Real ASGI requests serialize
    too narrowly to hit this window on demand, so the test holds the read.
    """
    async with _client() as client:
        await _create(client, "First")
        second = await _create(client, "Second")
        third = await _create(client, "Third")

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
        left_service = ProfileService(left, LOCAL_USER_ID)
        right_service = ProfileService(right, LOCAL_USER_ID)

        async def lose() -> None:
            with pytest.raises(DefaultProfileRaceError):
                await left_service.update(UUID(str(second["id"])), ProfileUpdate(is_default=True))

        async def win() -> None:
            await right_service.update(UUID(str(third["id"])), ProfileUpdate(is_default=True))
            sibling_done.set()

        await asyncio.gather(lose(), win())

    async with Session() as session:
        defaults = await session.scalar(
            text("SELECT count(*) FROM provider_profiles WHERE is_default")
        )
        holder = await session.scalar(text("SELECT name FROM provider_profiles WHERE is_default"))
    assert (defaults, holder) == (1, "Third")


async def test_a_lost_swap_on_patch_is_a_named_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """The update route maps the service's race to 409, never a bare 500."""
    async with _client() as client:
        profile = await _create(client)

        async def lost(self: ProfileService, profile_id: UUID, payload: ProfileUpdate) -> None:
            raise DefaultProfileRaceError("another swap made its profile the default first")

        monkeypatch.setattr(ProfileService, "update", lost)
        response = await client.patch(
            f"/api/settings/profiles/{profile['id']}", json={"is_default": True}
        )
    assert response.status_code == 409
    assert "default" in response.json()["detail"]


async def test_set_default_flips_the_old_default_out_before_raising_the_new() -> None:
    """The swap keeps a single default through both flushes, index in force."""
    async with _client() as client:
        await _create(client, "First")
        second = await _create(client, "Second")

    async with Session() as session:
        await ProfileService(session, LOCAL_USER_ID).set_default(UUID(str(second["id"])))

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


async def test_a_profile_cannot_be_patched_out_of_being_the_default() -> None:
    """``is_default: false`` would leave the user without one; it is refused."""
    async with _client() as client:
        profile = await _create(client)
        response = await client.patch(
            f"/api/settings/profiles/{profile['id']}", json={"is_default": False}
        )
        assert response.status_code == 422
        assert "is_default" in response.text


async def test_the_default_profile_cannot_be_deleted_and_the_error_names_the_way_out() -> None:
    """The only-default profile's DELETE is a 409 that says how to proceed."""
    async with _client() as client:
        profile = await _create(client)
        response = await client.delete(f"/api/settings/profiles/{profile['id']}")
        assert response.status_code == 409
        assert "second" in response.json()["detail"]
        listed = (await client.get("/api/settings/profiles")).json()
        assert [str(p["id"]) for p in listed] == [str(profile["id"])]


async def test_deleting_a_profile_cascades_its_assignments() -> None:
    """A deleted non-default profile takes its assignments with it."""
    async with _client() as client:
        await _create(client, "Default")
        doomed = await _create(client, "Doomed")
        assigned = await client.put(
            "/api/settings/assignments/chat.ask", json={"profile_id": doomed["id"]}
        )
        assert assigned.status_code == 200

        deleted = await client.delete(f"/api/settings/profiles/{doomed['id']}")
        assert deleted.status_code == 204

        assert (await client.get("/api/settings/assignments")).json() == []


async def test_a_half_configured_profile_is_refused_with_named_fields() -> None:
    """``openai-chat`` needs a model, and a key when the endpoint is remote."""
    async with _client() as client:
        no_model = await client.post(
            "/api/settings/profiles",
            json={"name": "Ohne Modell", "kind": "openai-chat", "api_key": SECRET},
        )
        assert no_model.status_code == 422
        assert "model" in no_model.text

        remote_without_key = await client.post(
            "/api/settings/profiles",
            json={"name": "Fern", "kind": "openai-chat", "base_url": REMOTE},
        )
        assert remote_without_key.status_code == 422
        assert "api_key" in remote_without_key.text

        unknown_kind = await client.post(
            "/api/settings/profiles", json={"name": "Art", "kind": "anthropic"}
        )
        assert unknown_kind.status_code == 422
        assert "kind" in unknown_kind.text

        # Nothing half-configured was stored.
        assert (await client.get("/api/settings/profiles")).json() == []


async def test_an_update_can_half_configure_a_profile_and_is_refused() -> None:
    """Clearing the model of an openai-chat profile is refused where it happens."""
    async with _client() as client:
        profile = await _create(client)
        response = await client.patch(
            f"/api/settings/profiles/{profile['id']}", json={"model": None}
        )
        assert response.status_code == 422
        assert "model" in response.text
        assert (await client.get("/api/settings/profiles")).json()[0]["model"] == "vendor-mini"


async def test_a_remote_http_endpoint_carrying_a_key_is_refused() -> None:
    """A key would cross the network in cleartext: the gate refuses the URL."""
    async with _client() as client:
        clear = await client.post(
            "/api/settings/profiles",
            json={
                "name": "Klar",
                "kind": "openai-chat",
                "base_url": "http://api.vendor.example/v1",
                "model": "vendor-mini",
                "api_key": SECRET,
            },
        )
        assert clear.status_code == 422
        assert "base_url" in clear.text
        assert (await client.get("/api/settings/profiles")).json() == []

        # The secure twin saves, so the refusal is the scheme's, not the remote host's.
        secure = await client.post(
            "/api/settings/profiles",
            json={
                "name": "Sicher",
                "kind": "openai-chat",
                "base_url": REMOTE,
                "model": "vendor-mini",
                "api_key": SECRET,
            },
        )
        assert secure.status_code == 201, secure.text


async def test_a_bare_endpoint_without_scheme_is_refused() -> None:
    """``not-a-url`` has no host, so it counts as remote and never as https."""
    async with _client() as client:
        response = await client.post(
            "/api/settings/profiles",
            json={
                "name": "Kaputt",
                "kind": "openai-chat",
                "base_url": "not-a-url",
                "model": "vendor-mini",
                "api_key": SECRET,
            },
        )
        assert response.status_code == 422
        assert "base_url" in response.text


async def test_a_local_http_endpoint_still_needs_no_key() -> None:
    """Loopback plainly serves without a key; the scheme rule spares the local case."""
    async with _client() as client:
        response = await client.post(
            "/api/settings/profiles",
            json={
                "name": "Lokal ohne Schlüssel",
                "kind": "openai-chat",
                "base_url": "http://127.0.0.1:9/v1",
                "model": "vendor-mini",
            },
        )
        assert response.status_code == 201, response.text


async def test_a_patch_to_a_remote_http_endpoint_is_refused_with_a_stored_key() -> None:
    """Redirecting a stored credential to a cleartext endpoint is refused too."""
    async with _client() as client:
        profile = await _create(client, "Weiterleitung")
        response = await client.patch(
            f"/api/settings/profiles/{profile['id']}",
            json={"base_url": "http://api.vendor.example/v1"},
        )
        assert response.status_code == 422
        assert "base_url" in response.text
        stored = (await client.get("/api/settings/profiles")).json()[0]
        assert stored["base_url"] == "http://127.0.0.1:9/v1"


async def test_a_patch_cannot_clear_the_name() -> None:
    """``name`` is NOT NULL; a present null is refused with the field, not a 500."""
    async with _client() as client:
        profile = await _create(client, "Bleibt")
        response = await client.patch(
            f"/api/settings/profiles/{profile['id']}", json={"name": None}
        )
        assert response.status_code == 422
        assert "name" in response.text
        assert (await client.get("/api/settings/profiles")).json()[0]["name"] == "Bleibt"


async def test_an_output_reservation_that_leaves_no_input_room_is_refused() -> None:
    """``max_output_tokens`` must stay below ``context_window`` when both are set.

    Equality leaves a zero input budget and greater-than a negative one; the gate
    refuses both where the pair is known, so the allocator only ever sees ordered
    pairs (a catalog-merged degenerate pair is refused there, never clamped, D8).
    """
    payload = {
        "name": "Grenze",
        "kind": "openai-chat",
        "base_url": "http://127.0.0.1:9/v1",
        "model": "vendor-mini",
        "api_key": SECRET,
    }
    async with _client() as client:
        equal = await client.post(
            "/api/settings/profiles",
            json={**payload, "context_window": 1000, "max_output_tokens": 1000},
        )
        assert equal.status_code == 422
        assert "max_output_tokens" in equal.text

        greater = await client.post(
            "/api/settings/profiles",
            json={**payload, "context_window": 1000, "max_output_tokens": 2000},
        )
        assert greater.status_code == 422
        assert "max_output_tokens" in greater.text

        ordered = await client.post(
            "/api/settings/profiles",
            json={**payload, "context_window": 1000, "max_output_tokens": 200},
        )
        assert ordered.status_code == 201, ordered.text

        # Shrinking the window under the stored reservation is the same refusal.
        patched = await client.patch(
            f"/api/settings/profiles/{ordered.json()['id']}", json={"context_window": 150}
        )
        assert patched.status_code == 422
        assert "max_output_tokens" in patched.text


async def test_the_connection_test_hits_the_vendor_and_audits_settings_test() -> None:
    """One cheap completion against the endpoint, one ``settings.test`` audit row."""
    with chat_vendor() as vendor:
        async with _client() as client:
            profile = await _create(client, base_url=vendor.base_url)
            result = await client.post(f"/api/settings/profiles/{profile['id']}/test")

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
    assert str(row.profile_id) == str(profile["id"])
    assert row.cost_usd == 0.0  # the vendor is local: free, not unknown


async def test_a_failing_connection_test_reports_the_failure_and_audits_it() -> None:
    """A vendor refusal is a failed test result, not a failed HTTP request."""
    with chat_vendor() as vendor:
        vendor.refuse_requests()
        async with _client() as client:
            profile = await _create(client, base_url=vendor.base_url)
            result = await client.post(f"/api/settings/profiles/{profile['id']}/test")

    assert result.status_code == 200
    body = result.json()
    assert body["ok"] is False
    assert body["error"] is not None

    async with Session() as session:
        row = (await session.execute(text("SELECT status, error FROM llm_calls"))).one()
    assert row.status == "error"
    assert row.error is not None


async def test_a_profile_whose_key_is_lost_fails_the_test_by_name() -> None:
    """Undecryptable ciphertext is a failed test naming the profile, never a 500."""
    async with _client() as client:
        profile = await _create(client)
        profile_id = UUID(str(profile["id"]))
        async with Session() as session:
            await session.execute(
                text(
                    "UPDATE provider_profiles SET api_key = 'gAAAAA-not-ciphertext' WHERE id = :id"
                ),
                {"id": profile_id},
            )
            await session.commit()

        result = await client.post(f"/api/settings/profiles/{profile_id}/test")

    assert result.status_code == 200
    body = result.json()
    assert body["ok"] is False
    assert str(profile_id) in body["error"]


async def test_discovery_lists_the_vendors_models() -> None:
    """``GET {base_url}/models`` through the profile's endpoint and key."""
    with chat_vendor() as vendor:
        async with _client() as client:
            profile = await _create(client, base_url=vendor.base_url)
            listed = await client.get(f"/api/settings/profiles/{profile['id']}/models")

    assert listed.status_code == 200
    assert listed.json() == ["vendor-max", "vendor-mini"]
    [request] = vendor.received
    assert request["path"] == "/v1/models"
    assert request["headers"]["authorization"] == f"Bearer {SECRET}"


async def test_discovery_on_a_fake_profile_is_refused() -> None:
    """A fake profile has no endpoint to discover models on."""
    async with _client() as client:
        created = await client.post(
            "/api/settings/profiles", json={"name": "Geist", "kind": "fake"}
        )
        assert created.status_code == 201
        response = await client.get(f"/api/settings/profiles/{created.json()['id']}/models")
        assert response.status_code == 409


async def test_assignments_accept_unknown_forward_compatible_task_keys() -> None:
    """Any non-empty task key can be assigned and cleared, listed or not."""
    async with _client() as client:
        profile = await _create(client)
        assigned = await client.put(
            "/api/settings/assignments/brandnew.task", json={"profile_id": profile["id"]}
        )
        assert assigned.status_code == 200
        assert assigned.json() == {
            "task_key": "brandnew.task",
            "profile_id": profile["id"],
        }

        listed = (await client.get("/api/settings/assignments")).json()
        assert listed == [{"task_key": "brandnew.task", "profile_id": profile["id"]}]

        cleared = await client.put(
            "/api/settings/assignments/brandnew.task", json={"profile_id": None}
        )
        assert cleared.status_code == 200
        assert cleared.json()["profile_id"] is None
        assert (await client.get("/api/settings/assignments")).json() == []


async def test_an_assignment_for_a_missing_profile_is_refused() -> None:
    """Assigning a task to a profile that is not the user's is a 404."""
    async with _client() as client:
        response = await client.put(
            "/api/settings/assignments/chat.ask",
            json={"profile_id": "00000000-0000-0000-0000-000000000099"},
        )
        assert response.status_code == 404


async def test_a_missing_profile_is_a_404_on_every_named_route() -> None:
    """Patch, delete, test and discovery all name the missing profile the same way."""
    missing = "00000000-0000-0000-0000-000000000099"
    async with _client() as client:
        for method, path in (
            ("PATCH", f"/api/settings/profiles/{missing}"),
            ("DELETE", f"/api/settings/profiles/{missing}"),
            ("POST", f"/api/settings/profiles/{missing}/test"),
            ("GET", f"/api/settings/profiles/{missing}/models"),
        ):
            response = await client.request(method, path, json={} if method == "PATCH" else None)
            assert response.status_code == 404, (method, response.text)


async def test_a_raw_keyring_failure_becomes_the_named_refusal_not_a_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A keyring backend that dies mid-save surfaces as the closed 503 vocabulary."""
    from app.capabilities.settings import profiles_service

    def broken_save(profile_id: object, plaintext: str) -> str:
        raise KeyringError("the backend died between probe and write")

    monkeypatch.setattr(profiles_service, "save_key", broken_save)
    async with _client() as client:
        response = await client.post(
            "/api/settings/profiles",
            json={
                "name": "Kaputt",
                "kind": "openai-chat",
                "base_url": REMOTE,
                "model": "vendor-mini",
                "api_key": SECRET,
            },
        )
        assert response.status_code == 503
        assert (await client.get("/api/settings/profiles")).json() == []
