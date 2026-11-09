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
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from keyring.errors import KeyringError
from sqlalchemy import text

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.anthropic_messages import ANTHROPIC_VERSION
from app.kernel.llm.catalog import load_catalog, snapshot_date, vendor_models
from app.kernel.llm.models import LLMProvider, ProviderProfile
from app.kernel.llm.presets import PRESETS
from app.kernel.llm.repositories import ProfileRepository, ProviderRepository
from app.kernel.secrets import load_key
from app.kernel.testing.vendor import chat_vendor, list_vendor, messages_vendor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.timeout(30)

SECRET = "sk-test-secret"
REMOTE = "https://api.vendor.example/v1"
LOCAL = "http://127.0.0.1:9/v1"

OTHER = uuid4()


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

    Written the way the surface stores the pair: one provider, its model
    carrying the pointer and the model name (the routes do the same since
    the model write gate landed).
    """
    async with Session() as session:
        providers = ProviderRepository(session, LOCAL_USER_ID)
        provider = await providers.create(name="Vendor", kind="openai-chat", base_url=REMOTE)
        profiles = ProfileRepository(session, LOCAL_USER_ID)
        model = await profiles.create(name="GLM", provider_id=provider.id, model="GLM")
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


async def test_an_update_stores_the_normalized_base_url(client: AsyncClient) -> None:
    """The gate computes a stripped endpoint; the row stores that spelling.

    The create strips a trailing slash before it gates; an update that kept
    the payload's raw form would store an endpoint the key tier and the
    locality tier read differently than the gate vetted.
    """
    provider = await _create(client, "Schrägstrich")
    response = await client.patch(
        f"/api/settings/providers/{provider['id']}",
        json={"base_url": "http://127.0.0.1:9/v1///"},
    )
    assert response.status_code == 200, response.text
    stored = (await client.get("/api/settings/providers")).json()[0]
    assert stored["base_url"] == "http://127.0.0.1:9/v1"


async def test_replacing_the_key_updates_the_mask_and_the_old_key_stops_loading(
    client: AsyncClient,
) -> None:
    """A PATCH with a new key stores the new one; the old plaintext is gone.

    Replacement, not addition: the column names one key, so after the patch
    the tier produces the new plaintext and could not produce the old even
    if something still held it.
    """
    provider = await _create(client)
    provider_id = UUID(str(provider["id"]))
    (before, _hint_before) = await _stored(provider_id, "api_key", "api_key_hint")
    assert load_key(provider_id, str(before)) == SECRET

    replaced = await client.patch(
        f"/api/settings/providers/{provider_id}", json={"api_key": "sk-second-key"}
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["api_key_mask"] == "sk-…-key"  # the new key's last four

    (column, hint) = await _stored(provider_id, "api_key", "api_key_hint")
    assert load_key(provider_id, str(column)) == "sk-second-key"
    assert column != before
    assert hint == "-key"


async def test_another_users_provider_is_invisible_and_untouchable(
    client: AsyncClient,
) -> None:
    """The surface is user-scoped: another user's provider is 404 everywhere.

    The reads never list it, and a patch, a delete or a discovery against it
    names no row — the same not-found a missing id gets, so the answer does
    not leak that the id exists for someone else.
    """
    await seed_user(OTHER)
    async with Session() as session:
        theirs = await ProviderRepository(session, OTHER).create(
            name="Their vendor", kind="openai-chat", base_url=REMOTE, api_key="their-key"
        )
        await session.commit()

    listed = (await client.get("/api/settings/providers")).json()
    assert all(provider["id"] != str(theirs.id) for provider in listed)

    for method, path in (
        ("PATCH", f"/api/settings/providers/{theirs.id}"),
        ("DELETE", f"/api/settings/providers/{theirs.id}"),
        ("GET", f"/api/settings/providers/{theirs.id}/models"),
    ):
        response = await client.request(method, path, json={"name": "Stolen"})
        assert response.status_code == 404, (method, response.text)
        assert response.json()["detail"] == "provider not found"


async def test_an_update_renames_the_provider(client: AsyncClient) -> None:
    """The name is a patchable column: a rename lands and stays on reads.

    The patch loop must carry the name like any other column — a 200 that
    silently kept the old one passed here once, and only the E2E's rename
    step caught it.
    """
    provider = await _create(client, "Alter Name")
    response = await client.patch(
        f"/api/settings/providers/{provider['id']}", json={"name": "Neuer Name"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Neuer Name"
    stored = (await client.get("/api/settings/providers")).json()[0]
    assert stored["name"] == "Neuer Name"


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


async def test_a_delete_the_guard_cannot_see_still_refuses_as_a_409(
    client: AsyncClient,
) -> None:
    """The RESTRICT backstop: a model pointer the guard cannot see refuses too.

    The delete guard counts the *user's* models; a model row of another
    user pointing at this provider — unstoreable through the write gate,
    which is why only a direct insert can plant it — is invisible to that
    count. The FK's RESTRICT is the atomic backstop: the delete dies at the
    database and the route answers the same 409 the guard gives. Before the
    backstop this delete was a 204 that cascaded the stranger's model away.
    """
    provider = await _create(client)
    stranger = uuid4()
    async with Session() as session:
        await session.execute(
            text("INSERT INTO users (id, created_at) VALUES (:id, now())"), {"id": stranger}
        )
        await session.execute(
            text(
                "INSERT INTO provider_profiles (id, user_id, name, provider_id, is_default,"
                " created_at, updated_at)"
                " VALUES (:id, :user_id, 'Fremd', :provider_id, false, now(), now())"
            ),
            {"id": uuid4(), "user_id": stranger, "provider_id": provider["id"]},
        )
        await session.commit()

    refused = await client.delete(f"/api/settings/providers/{provider['id']}")

    assert refused.status_code == 409, refused.text
    assert "models" in refused.json()["detail"]
    # The pointer is intact: nothing cascaded away behind the refusal.
    async with Session() as session:
        still_there = await session.scalar(
            text("SELECT count(*) FROM provider_profiles WHERE user_id = :user"),
            {"user": stranger},
        )
    assert still_there == 1


async def test_a_half_configured_provider_is_refused_with_named_fields(
    client: AsyncClient,
) -> None:
    """A remote-kind provider needs a base URL — the row is the endpoint."""
    no_base_url = await client.post(
        "/api/settings/providers", json={"name": "Ohne Ziel", "kind": "openai-chat"}
    )
    assert no_base_url.status_code == 422
    assert "base_url" in no_base_url.text

    no_base_url_anthropic = await client.post(
        "/api/settings/providers", json={"name": "Ohne Ziel", "kind": "anthropic"}
    )
    assert no_base_url_anthropic.status_code == 422
    assert "base_url" in no_base_url_anthropic.text

    unknown_kind = await client.post(
        "/api/settings/providers", json={"name": "Art", "kind": "mistral"}
    )
    assert unknown_kind.status_code == 422
    assert "kind" in unknown_kind.text

    # Nothing half-configured was stored.
    assert (await client.get("/api/settings/providers")).json() == []


async def test_an_anthropic_provider_is_gated_like_openai_chat(client: AsyncClient) -> None:
    """The second remote kind: remote needs a key, and https when a key travels."""
    keyless_remote = await client.post(
        "/api/settings/providers",
        json={
            "name": "Ohne Schlüssel",
            "kind": "anthropic",
            "base_url": "https://api.anthropic.com/v1",
        },
    )
    assert keyless_remote.status_code == 422
    assert "api_key" in keyless_remote.text

    cleartext = await client.post(
        "/api/settings/providers",
        json={
            "name": "Klar",
            "kind": "anthropic",
            "base_url": "http://api.vendor.example",
            "api_key": SECRET,
        },
    )
    assert cleartext.status_code == 422
    assert "base_url" in cleartext.text

    # The secure twin saves, so the refusals were the key's and the scheme's,
    # not the kind's or the remote host's.
    secure = await client.post(
        "/api/settings/providers",
        json={
            "name": "Sicher",
            "kind": "anthropic",
            "base_url": "https://api.anthropic.com/v1",
            "api_key": SECRET,
        },
    )
    assert secure.status_code == 201, secure.text
    assert secure.json()["base_url"] == "https://api.anthropic.com/v1"


async def test_a_local_anthropic_endpoint_still_needs_no_key(client: AsyncClient) -> None:
    """Loopback plainly serves without a key, on the anthropic kind too."""
    response = await client.post(
        "/api/settings/providers",
        json={"name": "Lokal ohne Schlüssel", "kind": "anthropic", "base_url": LOCAL},
    )
    assert response.status_code == 201, response.text


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


async def test_discovery_asks_the_providers_own_list_url(client: AsyncClient) -> None:
    """``models_url`` is where the list lives: asked directly, base/models never.

    The OpenCode presets keep their list on a path of its own, off the chat
    base URL — discovery must ask the URL the row names, not the endpoint's
    conventional ``/models`` beside it.
    """
    with chat_vendor() as vendor:
        vendor.serve_models_at("/vendor-list/models")
        provider = await _create(
            client,
            base_url=vendor.base_url,
            models_url=f"{vendor.origin}/vendor-list/models",
        )
        listed = await client.get(f"/api/settings/providers/{provider['id']}/models")

    assert listed.status_code == 200, listed.text
    assert "vendor-mini" in listed.json()
    # The own list path was asked once, with the credential (the hosts are
    # the same); the ``/models`` path on the base URL was never asked.
    assert vendor.list_requests == 1
    assert vendor.last["path"] == "/vendor-list/models"
    assert vendor.last["headers"]["authorization"] == f"Bearer {SECRET}"
    assert all(entry["path"] != "/v1/models" for entry in vendor.received)


async def test_discovery_keeps_the_key_on_the_endpoint_host(client: AsyncClient) -> None:
    """A list on another host is asked anonymously: the key never arrives there.

    The chat vendor answers under ``127.0.0.1``, the list stand-in under
    ``localhost`` — a different host on the same machine — so a models URL
    pointed there proves the rule: the port routes the request, the host
    name keeps the credential away. The stand-in's catalog arrives unsorted
    and with one duplicate, so the parse's sort and dedupe are pinned too.
    """
    with chat_vendor() as vendor, list_vendor() as other:
        provider = await _create(
            client, base_url=vendor.base_url, models_url=f"{other.base_url}/models"
        )
        listed = await client.get(f"/api/settings/providers/{provider['id']}/models")

    assert listed.status_code == 200, listed.text
    assert listed.json() == ["vendor-max", "vendor-mini"]
    # The endpoint's own host was never asked either: only the list URL.
    assert vendor.received == []
    assert other.authorization is None
    assert "x-api-key" not in other.last["headers"]


async def test_discovery_keeps_the_anthropic_key_on_the_endpoint_host(
    client: AsyncClient,
) -> None:
    """An anthropic list on another host is asked anonymously: no key arrives there.

    The same rule as the bearer wire, other header: the messages vendor
    serves the endpoint under ``127.0.0.1``, the list stand-in under
    ``localhost`` — the version header still rides (protocol, not
    credential), the key stays home.
    """
    with messages_vendor() as vendor, list_vendor() as other:
        provider = await client.post(
            "/api/settings/providers",
            json={
                "name": "Anthropic",
                "kind": "anthropic",
                "base_url": vendor.base_url,
                "api_key": SECRET,
                "models_url": f"{other.base_url}/models",
            },
        )
        assert provider.status_code == 201, provider.text
        listed = await client.get(f"/api/settings/providers/{provider.json()['id']}/models")

    assert listed.status_code == 200, listed.text
    assert listed.json() == ["vendor-max", "vendor-mini"]  # sorted, deduplicated
    # The endpoint's own host was never asked; the list saw no credential.
    assert vendor.received == []
    assert "x-api-key" not in other.last["headers"]
    assert "authorization" not in other.last["headers"]
    # The protocol header is not a credential: it rides every anthropic ask.
    assert other.last["headers"]["anthropic-version"] == "2023-06-01"


async def test_discovery_keeps_the_key_to_the_endpoints_origin(client: AsyncClient) -> None:
    """A same-host list on another port is asked anonymously — the rule is the origin.

    The credential follows scheme AND host AND port, never the host name
    alone: a models_url that shares the endpoint's ``127.0.0.1`` but not its
    port answers from another server on this machine, and the key must stay
    home — on both wires, the bearer and ``x-api-key``. The host-only check
    this test replaces sent the credential to that other server.
    """
    with chat_vendor() as vendor, messages_vendor(), list_vendor() as other:
        provider = await _create(
            client,
            base_url=vendor.base_url,
            models_url=f"{other.loopback_url}/models",
        )
        listed = await client.get(f"/api/settings/providers/{provider['id']}/models")

    assert listed.status_code == 200, listed.text
    assert listed.json() == ["vendor-max", "vendor-mini"]
    # The endpoint was never asked; the same-host list saw no credential.
    assert vendor.received == []
    assert other.authorization is None
    assert "x-api-key" not in other.last["headers"]

    # The anthropic wire, same mistake barred: the version header is
    # protocol and rides, the key is a credential and does not.
    with messages_vendor() as vendor, list_vendor() as other:
        provider = await client.post(
            "/api/settings/providers",
            json={
                "name": "Anthropic",
                "kind": "anthropic",
                "base_url": vendor.base_url,
                "api_key": SECRET,
                "models_url": f"{other.loopback_url}/models",
            },
        )
        assert provider.status_code == 201, provider.text
        listed = await client.get(f"/api/settings/providers/{provider.json()['id']}/models")

    assert listed.status_code == 200, listed.text
    assert "x-api-key" not in other.last["headers"]
    assert "authorization" not in other.last["headers"]
    assert other.last["headers"]["anthropic-version"] == ANTHROPIC_VERSION


async def test_discovery_asks_an_anthropic_provider_for_its_models(
    client: AsyncClient,
) -> None:
    """The anthropic wire: its own list route, ``x-api-key`` and the version header."""
    with messages_vendor() as vendor:
        provider = await client.post(
            "/api/settings/providers",
            json={
                "name": "Anthropic",
                "kind": "anthropic",
                "base_url": vendor.base_url,
                "api_key": SECRET,
            },
        )
        assert provider.status_code == 201, provider.text
        listed = await client.get(f"/api/settings/providers/{provider.json()['id']}/models")

    assert listed.status_code == 200, listed.text
    assert listed.json() == ["vendor-large", "vendor-small"]
    [request] = vendor.received
    assert request["path"] == "/v1/models"
    assert request["headers"]["x-api-key"] == SECRET
    assert request["headers"]["anthropic-version"] == "2023-06-01"
    # The bearer scheme is the other wire's: none of it here.
    assert "authorization" not in request["headers"]


async def test_a_keyless_local_endpoint_is_asked_without_a_credential(
    client: AsyncClient,
) -> None:
    """No key stored, loopback endpoint: the discovery request carries none."""
    with chat_vendor() as vendor:
        provider = await client.post(
            "/api/settings/providers",
            json={"name": "Lokal", "kind": "openai-chat", "base_url": vendor.base_url},
        )
        assert provider.status_code == 201, provider.text
        listed = await client.get(f"/api/settings/providers/{provider.json()['id']}/models")

    assert listed.status_code == 200, listed.text
    assert listed.json() == ["vendor-max", "vendor-mini"]
    assert "authorization" not in vendor.last["headers"]


async def test_an_unreachable_endpoint_fails_discovery_as_a_502(client: AsyncClient) -> None:
    """A transport failure is the router's 502, not a traceback or an empty list."""
    provider = await _create(client, base_url=LOCAL)
    response = await client.get(f"/api/settings/providers/{provider['id']}/models")
    assert response.status_code == 502


async def test_a_refusing_endpoint_fails_discovery_as_a_502(client: AsyncClient) -> None:
    """An endpoint that answers 401 to the list request maps to the same 502."""
    with chat_vendor() as vendor:
        provider = await _create(client, base_url=vendor.base_url)
        vendor.refuse_requests()
        response = await client.get(f"/api/settings/providers/{provider['id']}/models")

    assert response.status_code == 502


async def test_a_redirecting_list_url_fails_discovery_as_a_502(client: AsyncClient) -> None:
    """A redirect is not a list: the hop is refused, and no second request runs.

    The saved URL is answered 302 — following it would carry the ask,
    credential included, to wherever the endpoint points (a redirect is a
    new host answering, the one place the key-withholding rule cannot
    look). httpx follows no redirect by default, so the answer is the
    router's 502: one request on the wire, its key on its own host.
    """
    with chat_vendor() as vendor:
        provider = await _create(client, base_url=vendor.base_url)
        vendor.redirect_models()
        response = await client.get(f"/api/settings/providers/{provider['id']}/models")

    assert response.status_code == 502
    [request] = vendor.received
    assert request["headers"]["authorization"] == f"Bearer {SECRET}"


async def test_a_list_body_that_is_not_the_wires_shape_fails_as_a_502(
    client: AsyncClient,
) -> None:
    """Non-JSON, a missing ``data`` list, entries without ``id``: 502, never a 500.

    A lying endpoint is a failed discovery, not a crash — every malformed
    shape lands in the router's closed answer, the way an unreachable one
    does. The ids come from real bytes on a real socket.
    """
    with list_vendor() as other:
        provider = await _create(client, base_url=LOCAL, models_url=f"{other.base_url}/models")
        other.serve_body(b"<html>not the wire</html>")
        not_json = await client.get(f"/api/settings/providers/{provider['id']}/models")
        other.serve_body(b'{"object": "list"}')
        no_data = await client.get(f"/api/settings/providers/{provider['id']}/models")
        other.serve_body(b'{"data": {"id": "one-object-where-a-list-belongs"}}')
        not_a_list = await client.get(f"/api/settings/providers/{provider['id']}/models")
        other.serve_body(b'{"data": [{"object": "model"}]}')
        no_id = await client.get(f"/api/settings/providers/{provider['id']}/models")

    for response in (not_json, no_data, not_a_list, no_id):
        assert response.status_code == 502, response.text


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


# The presets: the create form's one read, and the picker vocabulary it carries.


async def test_the_presets_list_the_nine_with_their_catalog_models(
    client: AsyncClient,
) -> None:
    """Every preset with its picker vocabulary and the snapshot's date.

    The models are the vendor's catalog ids — bare, sorted — and the date is
    the snapshot's own: the picker's honesty mark rides the same response,
    so the form needs no second call. The Coding Plan preset carries its
    note key; the OpenCode presets keep their model list's own URL.
    """
    response = await client.get("/api/settings/presets")
    assert response.status_code == 200
    presets = response.json()
    assert [entry["id"] for entry in presets] == [entry.id for entry in PRESETS]

    coding = presets[-1]
    assert coding["label"] == "Z.ai Coding Plan"
    assert coding["kind"] == "openai-chat"
    assert coding["base_url"] == "https://api.z.ai/api/coding/paas/v4"
    assert coding["models_url"] is None
    assert coding["vendor"] == "zai-coding-plan"
    assert coding["model"] == "glm-5.3"
    assert coding["note_key"] == "settings.providers.note.zaiCodingPlan"
    assert coding["models"] == sorted(
        entry.split("/", 1)[1] for entry in load_catalog() if entry.startswith("zai-coding-plan/")
    )
    assert coding["snapshot_date"] == snapshot_date()

    opencode = next(entry for entry in presets if entry["id"] == "opencode")
    assert opencode["models_url"] == "https://opencode.ai/inference/v1/models"
    # A vendor the catalog carries fills its preset's list — none ships empty.
    assert all(entry["models"] for entry in presets)


async def test_the_preset_join_is_built_once_per_process(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second read re-serves the cache; the snapshot is scanned once.

    The catalog is static, so the join is per process: a settings visit must
    not re-walk the 2.5 MB snapshot per request.
    """
    from app.capabilities.settings import providers_service

    reads = 0

    def counting_vendor_models(vendor: str) -> tuple[str, ...]:
        nonlocal reads
        reads += 1
        return vendor_models(vendor)

    monkeypatch.setattr(providers_service, "_preset_cache", None)
    monkeypatch.setattr(providers_service, "vendor_models", counting_vendor_models)
    first = await client.get("/api/settings/presets")
    second = await client.get("/api/settings/presets")
    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    assert reads == len(PRESETS)  # the first read built the join; the second walked the cache
