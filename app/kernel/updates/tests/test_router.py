"""The updates routes: the shell's one read and its dismissal.

The shape is the generated client's contract; the dismissal survives the next
read the way a reload must not bring the banner back. Before setup the read is
the same 409 every user-owned route answers.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.user import User
from app.kernel.db.session import Session
from app.kernel.testing.release_vendor import ReleaseVendor
from app.kernel.version import __version__

pytestmark = pytest.mark.timeout(30)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _forget_the_user() -> None:
    async with Session() as session:
        await session.execute(delete(User))
        await session.commit()


async def test_the_read_answers_the_update_shape(vendor: ReleaseVendor) -> None:
    async with _client() as client:
        response = await client.get("/api/updates")

    assert response.status_code == 200
    body = response.json()
    assert body["current_version"] == __version__
    assert body["latest_version"] == "v999.0.0"
    assert body["update_available"] is True
    assert body["release_notes"] == "## Notes\n\n- new"
    assert body["release_url"] == "https://example.test/release"
    assert body["dismissed"] is False
    assert body["checked_at"] is not None


async def test_dismissing_the_version_stops_the_banner(vendor: ReleaseVendor) -> None:
    async with _client() as client:
        first = await client.get("/api/updates")
        assert first.json()["update_available"] is True

        dismissed = await client.post("/api/updates/dismiss", json={"version": "v999.0.0"})
        assert dismissed.status_code == 200
        assert dismissed.json()["dismissed"] is True
        assert dismissed.json()["update_available"] is False

        second = await client.get("/api/updates")
        assert second.status_code == 200
        assert second.json()["update_available"] is False
        assert second.json()["dismissed"] is True


async def test_reading_before_setup_is_refused() -> None:
    await _forget_the_user()

    async with _client() as client:
        response = await client.get("/api/updates")

    assert response.status_code == 409
    assert response.json() == {"detail": "setup required"}


async def test_dismissing_before_setup_is_refused() -> None:
    await _forget_the_user()

    async with _client() as client:
        response = await client.post("/api/updates/dismiss", json={"version": "v999.0.0"})

    assert response.status_code == 409
    assert response.json() == {"detail": "setup required"}


async def test_an_over_long_version_is_refused() -> None:
    """The version column is 64 characters; the gate refuses more, not Postgres."""
    async with _client() as client:
        response = await client.post("/api/updates/dismiss", json={"version": "v" * 65})

    assert response.status_code == 422


async def test_the_dismissal_is_stored_for_the_local_user(vendor: ReleaseVendor) -> None:
    async with _client() as client:
        await client.post("/api/updates/dismiss", json={"version": "v999.0.0"})

    async with Session() as session:
        stored = await session.get(User, LOCAL_USER_ID)
        assert stored is not None
        assert stored.dismissed_update_version == "v999.0.0"
