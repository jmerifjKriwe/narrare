"""The provider surface: CRUD, masked keys, the gate, the delete guard.

The provider row is the endpoint a model names instead of repeating: the base
URL, the vendor, the key. Everything these tests pin follows from the key
being the one secret the row holds — the full key appears in exactly one
response (the create), every later read shows the mask, the stored column is
ciphertext — plus the half-configuration gate that refuses a provider which
could never answer, and the delete guard that names the models still pointed
at the provider instead of a count.
"""

from typing import TYPE_CHECKING

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from keyring.errors import KeyringError
from sqlalchemy import text

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.llm.models import LLMProvider, ProviderProfile
from app.kernel.llm.repositories import ProfileRepository, ProviderRepository
from app.kernel.testing.vendor import chat_vendor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.timeout(30)

SECRET = "sk-test-secret"
REMOTE = "https://api.vendor.example/v1"


@pytest.fixture(autouse=True)
def fernet_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Fernet tier: every test stores keys as ciphertext, never a keychain."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """An HTTP client that drives the real application through ASGI."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def seeded_model() -> ProviderProfile:
    """A provider with one model pointed at it, seeded straight into the tables.

    No API route points a profile at a provider yet — the cut that moves the
    pointer behind a route is a later task — so the rows are written the way
    the Task 1 backfill left them: one provider, its profile carrying the
    pointer and the model name.
    """
    async with Session() as session:
        providers = ProviderRepository(session, LOCAL_USER_ID)
        provider = await providers.create(name="Vendor", kind="openai-chat", base_url=REMOTE)
        profiles = ProfileRepository(session, LOCAL_USER_ID)
        model = await profiles.create(
            name="GLM", kind="openai-chat", provider_id=provider.id, model="GLM"
        )
        await session.commit()
    return model


async def _create(
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


async def _stored(provider_id: object, *columns: str) -> tuple[object, ...]:
    """The provider's stored columns, fresh from the table."""
    async with Session() as session:
        provider = await session.get(LLMProvider, provider_id)  # pyright: ignore[reportArgumentType]
    assert provider is not None
    return tuple(getattr(provider, column) for column in columns)


async def test_a_remote_provider_without_a_key_is_refused(client: AsyncClient) -> None:
    """The gate: a remote endpoint without a key could never answer."""
    response = await client.post(
        "/api/settings/providers",
        json={
            "name": "Vendor",
            "kind": "openai-chat",
            "base_url": "https://api.vendor.example/v1",
        },
    )
    assert response.status_code == 422
    assert "api_key" in response.text


async def test_a_provider_with_models_cannot_be_deleted(
    client: AsyncClient, seeded_model: ProviderProfile
) -> None:
    """The delete guard names the models, not a count."""
    response = await client.delete(f"/api/settings/providers/{seeded_model.provider_id}")
    assert response.status_code == 409
    assert "GLM" in response.json()["detail"]  # names the model, not a count


async def test_create_returns_the_full_key_once_and_masks_every_read_after(
    client: AsyncClient,
) -> None:
    """The one full-key response is the create; every later read shows the mask."""
    created = await _create(client)
    provider_id = created["id"]
    assert created["api_key"] == SECRET  # exactly once, here
    assert created["api_key_mask"] == "sk-…cret"

    listed = (await client.get("/api/settings/providers")).json()
    assert listed[0]["api_key_mask"] == "sk-…cret"
    assert "api_key" not in listed[0]

    renamed = await client.patch(f"/api/settings/providers/{provider_id}", json={"name": "Renamed"})
    assert renamed.status_code == 200
    assert renamed.json()["api_key_mask"] == "sk-…cret"
    assert "api_key" not in renamed.json()

    # The stored column is ciphertext: the plaintext never touches the table.
    (column, hint) = await _stored(provider_id, "api_key", "api_key_hint")
    assert column != SECRET
    assert SECRET not in str(column)
    assert hint == "cret"


async def test_the_list_is_ordered_by_name(client: AsyncClient) -> None:
    """``ordered`` is by name: the list's order does not follow insertion."""
    await _create(client, "Beta")
    await _create(client, "Alpha")
    listed = (await client.get("/api/settings/providers")).json()
    assert [provider["name"] for provider in listed] == ["Alpha", "Beta"]


async def test_an_update_with_an_empty_key_keeps_the_stored_one(client: AsyncClient) -> None:
    """An empty ``api_key`` in an update means "keep the stored key", not "clear"."""
    provider = await _create(client)
    provider_id = provider["id"]
    before = await _stored(provider_id, "api_key")

    for payload in ({"name": "Umbenannt"}, {"api_key": ""}, {"api_key": None}):
        response = await client.patch(f"/api/settings/providers/{provider_id}", json=payload)
        assert response.status_code == 200, response.text
        assert response.json()["api_key_mask"] == "sk-…cret"

    assert await _stored(provider_id, "api_key") == before


async def test_deleting_a_provider_without_models_removes_the_row(client: AsyncClient) -> None:
    """A provider nothing points at deletes; the list is empty afterwards."""
    provider = await _create(client)
    deleted = await client.delete(f"/api/settings/providers/{provider['id']}")
    assert deleted.status_code == 204
    assert (await client.get("/api/settings/providers")).json() == []


async def test_a_half_configured_provider_is_refused_with_named_fields(
    client: AsyncClient,
) -> None:
    """An openai-chat provider needs a base URL — the row is the endpoint."""
    no_base_url = await client.post(
        "/api/settings/providers", json={"name": "Ohne Ziel", "kind": "openai-chat"}
    )
    assert no_base_url.status_code == 422
    assert "base_url" in no_base_url.text

    unknown_kind = await client.post(
        "/api/settings/providers", json={"name": "Art", "kind": "anthropic"}
    )
    assert unknown_kind.status_code == 422
    assert "kind" in unknown_kind.text

    # Nothing half-configured was stored.
    assert (await client.get("/api/settings/providers")).json() == []


async def test_a_remote_http_endpoint_carrying_a_key_is_refused(client: AsyncClient) -> None:
    """A key would cross the network in cleartext: the gate refuses the URL."""
    clear = await client.post(
        "/api/settings/providers",
        json={
            "name": "Klar",
            "kind": "openai-chat",
            "base_url": "http://api.vendor.example/v1",
            "api_key": SECRET,
        },
    )
    assert clear.status_code == 422
    assert "base_url" in clear.text
    assert (await client.get("/api/settings/providers")).json() == []

    # The secure twin saves, so the refusal is the scheme's, not the remote host's.
    secure = await client.post(
        "/api/settings/providers",
        json={"name": "Sicher", "kind": "openai-chat", "base_url": REMOTE, "api_key": SECRET},
    )
    assert secure.status_code == 201, secure.text


async def test_a_bare_endpoint_without_scheme_is_refused(client: AsyncClient) -> None:
    """``not-a-url`` has no host, so it counts as remote and never as https."""
    response = await client.post(
        "/api/settings/providers",
        json={"name": "Kaputt", "kind": "openai-chat", "base_url": "not-a-url"},
    )
    assert response.status_code == 422
    assert "base_url" in response.text


async def test_a_local_endpoint_still_needs_no_key(client: AsyncClient) -> None:
    """Loopback plainly serves without a key; the scheme rule spares the local case."""
    response = await client.post(
        "/api/settings/providers",
        json={
            "name": "Lokal ohne Schlüssel",
            "kind": "openai-chat",
            "base_url": "http://127.0.0.1:9/v1",
        },
    )
    assert response.status_code == 201, response.text


async def test_a_patch_to_a_remote_http_endpoint_is_refused_with_a_stored_key(
    client: AsyncClient,
) -> None:
    """Redirecting a stored credential to a cleartext endpoint is refused too."""
    provider = await _create(client, "Weiterleitung")
    response = await client.patch(
        f"/api/settings/providers/{provider['id']}",
        json={"base_url": "http://api.vendor.example/v1"},
    )
    assert response.status_code == 422
    assert "base_url" in response.text
    stored = (await client.get("/api/settings/providers")).json()[0]
    assert stored["base_url"] == "http://127.0.0.1:9/v1"


async def test_a_patch_cannot_clear_the_name(client: AsyncClient) -> None:
    """``name`` is NOT NULL; a present null is refused with the field, not a 500."""
    provider = await _create(client, "Bleibt")
    response = await client.patch(f"/api/settings/providers/{provider['id']}", json={"name": None})
    assert response.status_code == 422
    assert "name" in response.text
    assert (await client.get("/api/settings/providers")).json()[0]["name"] == "Bleibt"


async def test_a_fake_provider_needs_no_endpoint_and_discovery_is_refused(
    client: AsyncClient,
) -> None:
    """A fake has no endpoint to name and none to discover models on."""
    created = await client.post("/api/settings/providers", json={"name": "Geist", "kind": "fake"})
    assert created.status_code == 201
    body = created.json()
    assert body["base_url"] is None
    assert body["api_key"] is None  # nothing was stored, nothing to confirm

    response = await client.get(f"/api/settings/providers/{body['id']}/models")
    assert response.status_code == 409


async def test_discovery_lists_the_vendors_models(client: AsyncClient) -> None:
    """``GET {base_url}/models`` through the provider's endpoint and key."""
    with chat_vendor() as vendor:
        provider = await _create(client, base_url=vendor.base_url)
        listed = await client.get(f"/api/settings/providers/{provider['id']}/models")

    assert listed.status_code == 200
    assert listed.json() == ["vendor-max", "vendor-mini"]
    [request] = vendor.received
    assert request["path"] == "/v1/models"
    assert request["headers"]["authorization"] == f"Bearer {SECRET}"


async def test_a_provider_whose_key_is_lost_fails_discovery_by_name(
    client: AsyncClient,
) -> None:
    """Undecryptable ciphertext is a 502 naming the provider, never a 500."""
    provider = await _create(client, base_url=REMOTE)
    provider_id = provider["id"]
    async with Session() as session:
        await session.execute(
            text("UPDATE llm_providers SET api_key = 'gAAAAA-not-ciphertext' WHERE id = :id"),
            {"id": provider_id},
        )
        await session.commit()

    response = await client.get(f"/api/settings/providers/{provider_id}/models")
    assert response.status_code == 502
    assert str(provider_id) in response.json()["detail"]


async def test_a_missing_provider_is_a_404_on_every_named_route(client: AsyncClient) -> None:
    """Patch, delete and discovery all name the missing provider the same way."""
    missing = "00000000-0000-0000-0000-000000000099"
    for method, path in (
        ("PATCH", f"/api/settings/providers/{missing}"),
        ("DELETE", f"/api/settings/providers/{missing}"),
        ("GET", f"/api/settings/providers/{missing}/models"),
    ):
        response = await client.request(method, path, json={} if method == "PATCH" else None)
        assert response.status_code == 404, (method, response.text)
        assert response.json()["detail"] == "provider not found"


async def test_a_raw_keyring_failure_becomes_the_named_refusal_not_a_500(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A keyring backend that dies mid-save surfaces as the closed 503 vocabulary."""
    from app.capabilities.settings import providers_service

    def broken_save(provider_id: object, plaintext: str) -> str:
        raise KeyringError("the backend died between probe and write")

    monkeypatch.setattr(providers_service, "save_key", broken_save)
    response = await client.post(
        "/api/settings/providers",
        json={"name": "Kaputt", "kind": "openai-chat", "base_url": REMOTE, "api_key": SECRET},
    )
    assert response.status_code == 503
    assert (await client.get("/api/settings/providers")).json() == []
