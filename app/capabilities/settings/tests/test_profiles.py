"""The provider-profile surface: CRUD, masked keys, defaults, assignments, probes.

The API key is the one secret the settings hold; everything these tests pin
follows from that: the full key appears in exactly one response (the create),
every later read shows the mask, the stored column is ciphertext, and a key
its tier can no longer produce fails by naming the profile — never the key.
The default guard, the cascade, the half-configuration refusals and the two
probes (test, discovery) run against the stand-in chat vendor over real HTTP.
"""

from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from keyring.errors import KeyringError
from sqlalchemy import text

from app.api.main import app
from app.kernel.db.session import Session
from app.kernel.llm.models import ProviderProfile
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
