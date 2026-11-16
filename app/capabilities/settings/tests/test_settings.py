"""The chosen language is user data: it is written once and read from anywhere.

A browser store would pass a single-browser test and lose the choice on the next
device, on a cleared cache, or on a second window. The row is the record; the
browser only decides when nobody chose. The profile's answers (W4) ride the
same row: the author name and the atelier's daily goal are the user's, a
carried ``null`` clears them back to the email label and no goal, and an
absent field keeps the stored answer — the language switchers carry the
locale alone, and their body stays the contract it always was.
"""

from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.api.main import app
from app.capabilities.settings.schemas import SettingsUpdate
from app.capabilities.settings.service import SettingsService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import User
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(30)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")

# The unset row every read of a fresh instance answers: no choice, no label,
# no goal — the browser, the email and the neutral decide from there.
UNSET = {"locale": None, "theme": None, "author_name": None, "daily_goal_words": None}


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
    assert response.json() == UNSET


async def test_a_chosen_locale_is_stored_on_the_user_row() -> None:
    async with _client() as client:
        written = await client.patch("/api/settings", json={"locale": "de"})
        assert written.status_code == 200
        assert written.json() == UNSET | {"locale": "de"}
        assert (await client.get("/api/settings")).json() == UNSET | {"locale": "de"}

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert user.locale == "de"


async def test_an_unknown_locale_is_refused_and_changes_nothing() -> None:
    async with _client() as client:
        await client.patch("/api/settings", json={"locale": "de"})
        refused = await client.patch("/api/settings", json={"locale": "tlh"})
        assert refused.status_code == 422
        assert (await client.get("/api/settings")).json() == UNSET | {"locale": "de"}


async def test_an_omitted_locale_is_refused() -> None:
    # {} must not mean "clear": a broken client would silently reset the choice.
    async with _client() as client:
        await client.patch("/api/settings", json={"locale": "fr"})
        refused = await client.patch("/api/settings", json={})
        assert refused.status_code == 422
        assert (await client.get("/api/settings")).json() == UNSET | {"locale": "fr"}


async def test_null_returns_the_choice_to_the_browser() -> None:
    async with _client() as client:
        await client.patch("/api/settings", json={"locale": "fr"})
        cleared = await client.patch("/api/settings", json={"locale": None})

        assert cleared.status_code == 200
        assert cleared.json() == UNSET
        assert (await client.get("/api/settings")).json() == UNSET

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert user.locale is None


async def test_the_author_name_round_trips_through_the_user_row() -> None:
    async with _client() as client:
        written = await client.patch(
            "/api/settings", json={"locale": None, "author_name": "J. Autorin"}
        )
        assert written.status_code == 200
        assert written.json() == UNSET | {"author_name": "J. Autorin"}
        assert (await client.get("/api/settings")).json() == UNSET | {"author_name": "J. Autorin"}

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert user.author_name == "J. Autorin"


async def test_the_author_name_is_trimmed_and_whitespace_clears() -> None:
    async with _client() as client:
        trimmed = await client.patch(
            "/api/settings", json={"locale": None, "author_name": "  J. Autorin  "}
        )
        assert trimmed.status_code == 200
        assert trimmed.json()["author_name"] == "J. Autorin"

        # Whitespace-only is the honest unset: the email label answers again.
        cleared = await client.patch("/api/settings", json={"locale": None, "author_name": "   "})
        assert cleared.status_code == 200
        assert cleared.json()["author_name"] is None

        await client.patch("/api/settings", json={"locale": None, "author_name": "J. Autorin"})
        nulled = await client.patch("/api/settings", json={"locale": None, "author_name": None})
        assert nulled.status_code == 200
        assert nulled.json()["author_name"] is None

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert user.author_name is None


async def test_an_over_long_author_name_is_refused_and_changes_nothing() -> None:
    async with _client() as client:
        await client.patch("/api/settings", json={"locale": None, "author_name": "J. Autorin"})
        refused = await client.patch(
            "/api/settings", json={"locale": None, "author_name": "x" * 201}
        )
        assert refused.status_code == 422
        assert any(entry["loc"] == ["body", "author_name"] for entry in refused.json()["detail"])
        assert (await client.get("/api/settings")).json() == UNSET | {"author_name": "J. Autorin"}


async def test_the_longest_author_name_the_column_holds_is_accepted() -> None:
    async with _client() as client:
        written = await client.patch(
            "/api/settings", json={"locale": None, "author_name": "x" * 200}
        )
        assert written.status_code == 200
        assert written.json()["author_name"] == "x" * 200


async def test_the_daily_goal_round_trips_and_null_clears() -> None:
    async with _client() as client:
        written = await client.patch(
            "/api/settings", json={"locale": None, "daily_goal_words": 500}
        )
        assert written.status_code == 200
        assert written.json() == UNSET | {"daily_goal_words": 500}
        assert (await client.get("/api/settings")).json() == UNSET | {"daily_goal_words": 500}

        cleared = await client.patch(
            "/api/settings", json={"locale": None, "daily_goal_words": None}
        )
        assert cleared.status_code == 200
        assert cleared.json()["daily_goal_words"] is None

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert user.daily_goal_words is None


@pytest.mark.parametrize("value", [0, -1, 2_147_483_648])
async def test_a_daily_goal_outside_the_column_is_refused(value: int) -> None:
    """A goal counts from one, and the ceiling is the Integer column's own:
    a 422 at the gate, never an int32 overflow at the write."""
    async with _client() as client:
        await client.patch("/api/settings", json={"locale": None, "daily_goal_words": 500})
        refused = await client.patch(
            "/api/settings", json={"locale": None, "daily_goal_words": value}
        )
        assert refused.status_code == 422
        assert any(
            entry["loc"] == ["body", "daily_goal_words"] for entry in refused.json()["detail"]
        )
        assert (await client.get("/api/settings")).json() == UNSET | {"daily_goal_words": 500}


async def test_the_largest_daily_goal_the_column_holds_is_accepted() -> None:
    async with _client() as client:
        written = await client.patch(
            "/api/settings", json={"locale": None, "daily_goal_words": 2_147_483_647}
        )
        assert written.status_code == 200
        assert written.json()["daily_goal_words"] == 2_147_483_647


@pytest.mark.parametrize("field", ["author_name", "daily_goal_words"])
async def test_an_absent_profile_field_keeps_the_stored_answer(field: str) -> None:
    """Absent ≠ null on the profile fields: a body that does not carry one
    keeps it — the language switchers' locale-only body is the live proof —
    while a carried null clears it (the tests above)."""
    answers = {"locale": None, "author_name": "J. Autorin", "daily_goal_words": 500}
    async with _client() as client:
        await client.patch("/api/settings", json=answers)
        # The switchers' own body: the locale alone, no profile field.
        switched = await client.patch("/api/settings", json={"locale": "de"})
        assert switched.status_code == 200
        assert switched.json() == UNSET | answers | {"locale": "de"}
        assert (await client.get("/api/settings")).json() == UNSET | answers | {"locale": "de"}

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert getattr(user, field) == answers[field]


async def test_the_preference_patch_leaves_the_theme_alone() -> None:
    """The theme keeps its own door: the preference row's write carries the
    fields it owns and reads the theme back untouched."""
    async with _client() as client:
        await client.patch("/api/settings/theme", json={"theme": "dark"})
        written = await client.patch(
            "/api/settings", json={"locale": "de", "author_name": "J. Autorin"}
        )
        assert written.status_code == 200
        assert written.json() == UNSET | {
            "locale": "de",
            "theme": "dark",
            "author_name": "J. Autorin",
        }


async def test_reading_a_fresh_instance_creates_nothing() -> None:
    # The request path writes nothing but the request's own transaction (D14):
    # opening the app must not be what installs it.
    await _forget_the_user()

    async with _client() as client:
        assert (await client.get("/api/settings")).json() == UNSET

    async with Session() as session:
        assert await session.get(User, LOCAL_USER_ID) is None


async def test_choosing_preferences_before_setup_is_refused() -> None:
    await _forget_the_user()

    async with _client() as client:
        response = await client.patch(
            "/api/settings",
            json={"locale": "de", "author_name": "J. Autorin", "daily_goal_words": 500},
        )

    assert response.status_code == 409


async def test_the_settings_write_touches_only_its_own_user_row() -> None:
    """Rule 4 at the service seam: the service writes the row of the user it
    was built for — another user's answers are neither read nor overwritten."""
    await seed_user(OTHER_USER)
    async with Session() as session:
        theirs = SettingsService(session, OTHER_USER)
        await theirs.write(
            SettingsUpdate(locale="fr", author_name="Eux Autre", daily_goal_words=300)
        )

    async with _client() as client:
        written = await client.patch(
            "/api/settings",
            json={"locale": "de", "author_name": "J. Autorin", "daily_goal_words": 500},
        )
        assert written.status_code == 200
        # The local read answers the local row alone.
        assert (await client.get("/api/settings")).json() == UNSET | {
            "locale": "de",
            "author_name": "J. Autorin",
            "daily_goal_words": 500,
        }

    async with Session() as session:
        other = await session.get(User, OTHER_USER)
        assert other is not None
        assert (other.locale, other.author_name, other.daily_goal_words) == (
            "fr",
            "Eux Autre",
            300,
        )
        local = await session.get(User, LOCAL_USER_ID)
        assert local is not None
        assert (local.locale, local.author_name, local.daily_goal_words) == (
            "de",
            "J. Autorin",
            500,
        )
        # The read is scoped the same way: the other user's row, not the local one.
        read = await SettingsService(session, OTHER_USER).read()
        assert read is not None
        assert read.author_name == "Eux Autre"


async def test_a_user_who_never_chose_a_theme_follows_the_system() -> None:
    async with _client() as client:
        assert (await client.get("/api/settings")).json() == UNSET


async def test_a_chosen_theme_is_stored_on_the_user_row() -> None:
    async with _client() as client:
        written = await client.patch("/api/settings/theme", json={"theme": "dark"})
        assert written.status_code == 200
        assert written.json() == {"theme": "dark"}
        assert (await client.get("/api/settings")).json() == UNSET | {"theme": "dark"}

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert user.theme == "dark"


async def test_an_unknown_theme_is_refused_and_changes_nothing() -> None:
    async with _client() as client:
        await client.patch("/api/settings/theme", json={"theme": "dark"})
        refused = await client.patch("/api/settings/theme", json={"theme": "sepia"})
        assert refused.status_code == 422
        assert (await client.get("/api/settings")).json()["theme"] == "dark"


async def test_an_omitted_theme_is_refused() -> None:
    # {} must not mean "clear": a broken client would silently reset the choice.
    async with _client() as client:
        await client.patch("/api/settings/theme", json={"theme": "dark"})
        refused = await client.patch("/api/settings/theme", json={})
        assert refused.status_code == 422
        assert (await client.get("/api/settings")).json()["theme"] == "dark"


async def test_null_returns_the_theme_to_the_system() -> None:
    async with _client() as client:
        await client.patch("/api/settings/theme", json={"theme": "light"})
        cleared = await client.patch("/api/settings/theme", json={"theme": None})
        assert cleared.status_code == 200
        assert cleared.json() == {"theme": None}

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert user.theme is None


async def test_a_theme_write_before_setup_is_refused() -> None:
    await _forget_the_user()
    async with _client() as client:
        refused = await client.patch("/api/settings/theme", json={"theme": "dark"})
        assert refused.status_code == 409
        assert (await client.get("/api/settings")).json() == UNSET
