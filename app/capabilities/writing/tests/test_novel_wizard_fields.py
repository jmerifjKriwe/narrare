"""The wizard's settings ride the novel PATCH (W4 §5): the book-settings
family edits what setup bound — the word target, the typology, the dramatic
form, the AI role and the canon strictness — against the one shared
vocabulary the kernel contract holds. Absent ≠ null: a field the body does
not carry is no change, a carried ``null`` clears the answer back to the
honest unset, and a value outside the contract is a 422 naming the field.
"""

from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.capabilities.writing.repository import NovelRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")

# One whole set of wizard answers, the shape the book-settings dialog sends.
WIZARD_ANSWERS = {
    "target_words": 65000,
    "author_typology": "plantser",
    "dramatic_form": "three-act",
    "ai_role": "lektor",
    "canon_strictness": 4,
}


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_novel(client: AsyncClient, title: str) -> str:
    response = await client.post("/api/writing/novels", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def test_a_new_novel_has_no_wizard_answers() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        body = fetched.json()
        for field in WIZARD_ANSWERS:
            assert body[field] is None


async def test_the_wizard_settings_round_trip_through_patch_and_read() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        patched = await client.patch(f"/api/writing/novels/{novel_id}", json=WIZARD_ANSWERS)
        assert patched.status_code == 200
        for field, value in WIZARD_ANSWERS.items():
            assert patched.json()[field] == value

        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        for field, value in WIZARD_ANSWERS.items():
            assert fetched.json()[field] == value
        listed = await client.get("/api/writing/novels")
        for field, value in WIZARD_ANSWERS.items():
            assert listed.json()[0][field] == value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("author_typology", "bogus"),
        ("author_typology", "Plotter"),
        ("ai_role", "bogus"),
        ("ai_role", "Lektor"),
        ("canon_strictness", 0),
        ("canon_strictness", 6),
        ("target_words", 0),
        ("target_words", -1),
        # One past the Integer column's ceiling: a 422, never a DB overflow.
        ("target_words", 2_147_483_648),
        ("dramatic_form", "x" * 81),
    ],
)
async def test_a_value_outside_the_contract_is_refused_by_name(field: str, value: object) -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        refused = await client.patch(f"/api/writing/novels/{novel_id}", json={field: value})
        assert refused.status_code == 422
        assert refused.json()["detail"] == f"invalid {field}"
        # Nothing was written: the book still has no answer on that field.
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()[field] is None


async def test_the_boundaries_the_columns_hold_are_accepted() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        patched = await client.patch(
            f"/api/writing/novels/{novel_id}",
            json={
                "target_words": 2_147_483_647,
                "canon_strictness": 1,
                "dramatic_form": "x" * 80,
            },
        )
        assert patched.status_code == 200
        assert patched.json()["target_words"] == 2_147_483_647
        assert patched.json()["canon_strictness"] == 1
        assert patched.json()["dramatic_form"] == "x" * 80

        top = await client.patch(f"/api/writing/novels/{novel_id}", json={"canon_strictness": 5})
        assert top.status_code == 200
        assert top.json()["canon_strictness"] == 5


@pytest.mark.parametrize("field", list(WIZARD_ANSWERS))
async def test_a_carried_null_clears_only_that_field(field: str) -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await client.patch(f"/api/writing/novels/{novel_id}", json=WIZARD_ANSWERS)
        cleared = await client.patch(f"/api/writing/novels/{novel_id}", json={field: None})
        assert cleared.status_code == 200
        assert cleared.json()[field] is None
        # The other answers stand: a clear is one field's, not the row's.
        for other, value in WIZARD_ANSWERS.items():
            if other != field:
                assert cleared.json()[other] == value


async def test_absent_fields_are_not_changes() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await client.patch(f"/api/writing/novels/{novel_id}", json=WIZARD_ANSWERS)

        # A title edit carries no wizard field: the answers stand untouched.
        renamed = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"title": "Neuer Titel"}
        )
        assert renamed.status_code == 200
        for field, value in WIZARD_ANSWERS.items():
            assert renamed.json()[field] == value

        # An empty body carries nothing and changes nothing.
        empty = await client.patch(f"/api/writing/novels/{novel_id}", json={})
        assert empty.status_code == 200
        for field, value in WIZARD_ANSWERS.items():
            assert empty.json()[field] == value


async def test_the_wizard_patch_leaves_the_other_metadata_alone() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await client.patch(
            f"/api/writing/novels/{novel_id}",
            json={"author": "J. Autorin", "genre": "Literary", "status": "draft"},
        )
        patched = await client.patch(f"/api/writing/novels/{novel_id}", json=WIZARD_ANSWERS)
        assert patched.status_code == 200
        assert patched.json()["author"] == "J. Autorin"
        assert patched.json()["genre"] == "Literary"
        assert patched.json()["status"] == "draft"


async def test_the_setup_bound_answers_are_editable() -> None:
    """The dialog's inheritance note becomes true: what the wizard bound onto
    the row, the book-settings PATCH can change — the answers are the book's
    own, not a setup-only fact."""
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        async with Session() as session:
            novels = NovelRepository(session, LOCAL_USER_ID)
            novel = await novels.get(UUID(novel_id))
            assert novel is not None
            await novels.save(novel, {"author_typology": "plotter", "target_words": 50000})
            await session.commit()

        changed = await client.patch(
            f"/api/writing/novels/{novel_id}",
            json={"author_typology": "pantser", "target_words": 65000},
        )
        assert changed.status_code == 200
        assert changed.json()["author_typology"] == "pantser"
        assert changed.json()["target_words"] == 65000


async def test_a_foreign_novel_is_not_found() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        foreign = await NovelRepository(session, OTHER_USER).create("Fremdes Buch")
        await session.commit()

    async with _client() as client:
        refused = await client.patch(f"/api/writing/novels/{foreign.id}", json=WIZARD_ANSWERS)
        assert refused.status_code == 404
        assert (await client.get(f"/api/writing/novels/{foreign.id}")).status_code == 404

    # The foreign row holds no answer: the local user's write never reached it.
    async with Session() as session:
        reread = await NovelRepository(session, OTHER_USER).get(foreign.id)
        assert reread is not None
        assert reread.author_typology is None
        assert reread.target_words is None
