"""The chosen language is user data: it is written once and read from anywhere.

A browser store would pass a single-browser test and lose the choice on the next
device, on a cleared cache, or on a second window. The row is the record; the
browser only decides when nobody chose.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import User
from app.kernel.db.session import Session

pytestmark = pytest.mark.timeout(30)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _forget_the_user() -> None:
    async with Session() as session:
        await session.execute(delete(User))
        await session.commit()


async def test_a_user_who_never_chose_follows_the_browser() -> None:
    async with _client() as client:
        response = await client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {"locale": None}


async def test_a_chosen_locale_is_stored_on_the_user_row() -> None:
    async with _client() as client:
        written = await client.patch("/api/settings", json={"locale": "de"})
        assert written.status_code == 200
        assert written.json() == {"locale": "de"}
        assert (await client.get("/api/settings")).json() == {"locale": "de"}

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert user.locale == "de"


async def test_an_unknown_locale_is_refused_and_changes_nothing() -> None:
    async with _client() as client:
        await client.patch("/api/settings", json={"locale": "de"})
        refused = await client.patch("/api/settings", json={"locale": "tlh"})
        assert refused.status_code == 422
        assert (await client.get("/api/settings")).json() == {"locale": "de"}


async def test_an_omitted_locale_is_refused() -> None:
    # {} must not mean "clear": a broken client would silently reset the choice.
    async with _client() as client:
        await client.patch("/api/settings", json={"locale": "fr"})
        refused = await client.patch("/api/settings", json={})
        assert refused.status_code == 422
        assert (await client.get("/api/settings")).json() == {"locale": "fr"}


async def test_null_returns_the_choice_to_the_browser() -> None:
    async with _client() as client:
        await client.patch("/api/settings", json={"locale": "fr"})
        cleared = await client.patch("/api/settings", json={"locale": None})

        assert cleared.status_code == 200
        assert cleared.json() == {"locale": None}
        assert (await client.get("/api/settings")).json() == {"locale": None}

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert user.locale is None


async def test_reading_a_fresh_instance_creates_nothing() -> None:
    # The request path writes nothing but the request's own transaction (D14):
    # opening the app must not be what installs it.
    await _forget_the_user()

    async with _client() as client:
        assert (await client.get("/api/settings")).json() == {"locale": None}

    async with Session() as session:
        assert await session.get(User, LOCAL_USER_ID) is None


async def test_choosing_a_locale_before_setup_is_refused() -> None:
    await _forget_the_user()

    async with _client() as client:
        response = await client.patch("/api/settings", json={"locale": "de"})

    assert response.status_code == 409
