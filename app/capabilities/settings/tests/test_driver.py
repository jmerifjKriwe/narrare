"""The driver read: the instance's serving truth as one word.

``fake`` while every assignable task's serving tier is the local fake
adapter, ``configured`` once any provider adapter serves one — the tasks
read's own resolution reduced to one word, never a second derivation, so
the offline card's claim can never disagree with the task list's rows.
The read is resolution only: it writes nothing and contacts no endpoint.
"""

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.kernel.secrets import KeyUnavailableError

pytestmark = pytest.mark.timeout(30)


@pytest.fixture(autouse=True)
def fernet_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Fernet tier: configured providers store keys as ciphertext, never
    a keychain — the provider suite's own convention."""
    monkeypatch.setenv("NARRE_KEYRING", "off")
    monkeypatch.setenv("NARRE_SECRET_KEY", Fernet.generate_key().decode())


def _client() -> AsyncClient:
    """An HTTP client that drives the real application through ASGI."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_model(
    client: AsyncClient,
    name: str,
    kind: str = "fake",
    model: str = "fake-model",
) -> dict[str, object]:
    """Create one provider of ``kind`` and one model under it, both 201s."""
    payload: dict[str, object] = {"name": f"{name} Anbieter", "kind": kind}
    if kind != "fake":
        payload |= {"base_url": "http://127.0.0.1:9/v1", "api_key": f"sk-{name.lower()}"}
    provider = await client.post("/api/settings/providers", json=payload)
    assert provider.status_code == 201, provider.text
    created = await client.post(
        "/api/settings/models",
        json={"name": name, "provider_id": provider.json()["id"], "model": model},
    )
    assert created.status_code == 201, created.text
    return dict(created.json())


async def test_the_unconfigured_instance_answers_fake() -> None:
    """No model, no environment choice: the cascade's floor serves, and the
    read names it — the offline card's honest standing."""
    async with _client() as client:
        response = await client.get("/api/settings/driver")

    assert response.status_code == 200
    assert response.json() == {"kind": "fake"}


async def test_a_fake_provider_still_answers_fake() -> None:
    """A stored fake model is the fake adapter all the same: the default
    tier answers through it and the word does not move."""
    async with _client() as client:
        await _create_model(client, "Default")
        response = await client.get("/api/settings/driver")

    assert response.status_code == 200
    assert response.json() == {"kind": "fake"}


async def test_one_configured_provider_answers_configured() -> None:
    """One provider adapter on the default tier is enough: the instance is
    configured, whatever the remaining keys answer."""
    async with _client() as client:
        await _create_model(client, "Cloud", kind="openai-chat", model="vendor-mini")
        response = await client.get("/api/settings/driver")

    assert response.status_code == 200
    assert response.json() == {"kind": "configured"}


async def test_one_anthropic_provider_answers_configured_too() -> None:
    """The word names the fact that a provider answers, not which one: the
    anthropic adapter configures the instance exactly as the chat one does."""
    async with _client() as client:
        await _create_model(client, "Claude", kind="anthropic", model="vendor-sonnet")
        response = await client.get("/api/settings/driver")

    assert response.status_code == 200
    assert response.json() == {"kind": "configured"}


async def test_a_configured_environment_tier_answers_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The environment tier is a serving tier like the stored ones: an
    instance pointed at a real adapter by ``NARRE_LLM_PROVIDER`` alone —
    no rows at all — is configured."""
    monkeypatch.setenv("NARRE_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("NARRE_LLM_MODEL", "env-model")
    async with _client() as client:
        response = await client.get("/api/settings/driver")

    assert response.status_code == 200
    assert response.json() == {"kind": "configured"}


async def test_the_read_writes_nothing_and_audits_nothing() -> None:
    """Resolution is a read: no assignment is created, no call is recorded."""
    async with _client() as client:
        await _create_model(client, "Default")
        assert (await client.get("/api/settings/driver")).status_code == 200
        assignments = (await client.get("/api/settings/assignments")).json()

    assert assignments == []


async def test_a_lost_provider_key_is_a_named_502(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key its tier can no longer produce fails the read, as it fails the
    tasks read: the same resolution, so the same failure shape — the 502
    that names the row, and a card that claims nothing."""
    async with _client() as client:
        await _create_model(client, "Lost key", kind="openai-chat", model="vendor-mini")

        from app.kernel.llm import resolution

        def broken_key(profile_id: object, column: str) -> str:
            raise KeyUnavailableError("the stored key cannot be produced")

        monkeypatch.setattr(resolution, "load_key", broken_key)
        response = await client.get("/api/settings/driver")

    assert response.status_code == 502
    assert "key" in response.json()["detail"]
