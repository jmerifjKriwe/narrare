"""The interchange HTTP surface against the real database, disk and engine.

Export and import are a novel's door: the ZIP round trip preserves the novel,
the path export writes real files and refuses to shrink an existing export,
and the import needs exactly one source, refuses what it cannot parse, and
reports what it merged. No fakes at all.
"""

import asyncio
import io
import struct
import zipfile
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from starlette.datastructures import UploadFile

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Novel, User
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.interchange import (
    ChapterFile,
    EntityFile,
    NovelArchive,
    open_zip,
    parse_archive,
    serialize_archive,
    zip_bytes,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_novel(client: AsyncClient, title: str, chapter: str | None = None) -> UUID:
    """One novel through the API, optionally with one chapter; the id back."""
    created = await client.post("/api/writing/novels", json={"title": title})
    assert created.status_code == 201, created.text
    novel_id = UUID(created.json()["id"])
    if chapter is not None:
        made = await client.post(
            f"/api/writing/novels/{novel_id}/chapters", json={"title": chapter}
        )
        assert made.status_code == 201, made.text
    return novel_id


def _archive_zip(title: str) -> bytes:
    """A minimal valid archive as ZIP bytes: one chapter, one entity."""
    archive = NovelArchive(
        title=title,
        chapters=[ChapterFile(title="Kapitel eins", position=0, body="Der Anfang.\n")],
        entities=[EntityFile(name="Vega", type="location", aliases=[], tags=[], body="Station.\n")],
    )
    return zip_bytes(serialize_archive(archive))


def _encrypted_zip() -> bytes:
    """Valid ZIP bytes whose one entry claims encryption.

    `zipfile` refuses `read()` with RuntimeError ("password required") — the
    failure an archive from an encryption tool arrives with, not BadZipFile.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as bundle:
        bundle.writestr(zipfile.ZipInfo("secret.txt"), b"hello")
    data = bytearray(buffer.getvalue())
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        position = 0
        while (found := data.find(signature, position)) >= 0:
            flags = struct.unpack_from("<H", data, found + flag_offset)[0]
            struct.pack_into("<H", data, found + flag_offset, flags | 0x1)
            position = found + 4
    return bytes(data)


def _corrupted_zip() -> bytes:
    """Valid ZIP bytes whose one deflated entry carries a broken stream.

    The first payload byte is overwritten with an invalid deflate block type
    (BTYPE 11): `zipfile` surfaces that as `zlib.error` on `read()`, not as
    `BadZipFile` — the shape a damaged or truncated transfer arrives in. The
    archive is otherwise well-formed, so the container check passes it.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("metadata.json", b'{"title": "' + b"x" * 500 + b'"}')
    data = bytearray(buffer.getvalue())
    local = data.find(b"PK\x03\x04")
    name_length = struct.unpack_from("<H", data, local + 26)[0]
    extra_length = struct.unpack_from("<H", data, local + 28)[0]
    data[local + 30 + name_length + extra_length] = 0x07
    return bytes(data)


async def test_export_zip_round_trips() -> None:
    """mode=zip answers application/zip whose bytes parse back into the same novel."""
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel", chapter="Erstes Kapitel")

        response = await client.post(f"/api/writing/novels/{novel_id}/export", json={"mode": "zip"})

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert response.headers["content-disposition"] == 'attachment; filename="der-nebel.zip"'
        archive = parse_archive(open_zip(response.content))
        assert archive.title == "Der Nebel"
        assert [chapter.title for chapter in archive.chapters] == ["Erstes Kapitel"]


async def test_export_path_writes_and_refuses_non_empty_target(tmp_path: Path) -> None:
    """mode=path writes the archive to disk and refuses to shrink an existing one."""
    target = tmp_path / "export"
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel", chapter="Erstes Kapitel")

        done = await client.post(
            f"/api/writing/novels/{novel_id}/export", json={"mode": "path", "path": str(target)}
        )
        assert done.status_code == 200
        assert done.json() == {"path": str(target), "chapters": 1, "entities": 0}

        # Real files on disk, not just a receipt.
        assert (target / "metadata.json").is_file()
        assert [entry.name for entry in sorted((target / "chapters").glob("*.md"))] == [
            "00-erstes-kapitel.md"
        ]

        # A second export must not shrink the first.
        again = await client.post(
            f"/api/writing/novels/{novel_id}/export", json={"mode": "path", "path": str(target)}
        )
        assert again.status_code == 409
        assert again.json() == {"detail": {"code": "target_not_empty", "path": str(target)}}


async def test_export_path_unwritable_is_422_named(tmp_path: Path) -> None:
    """An unreachable target is a 422 naming `path`, carrying the OS reason."""
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"not a directory")
    target = blocker / "export"
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")

        response = await client.post(
            f"/api/writing/novels/{novel_id}/export",
            json={"mode": "path", "path": str(target)},
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert ["body", "path"] in [entry["loc"] for entry in detail]
        assert "Not a directory" in detail[0]["msg"]


async def test_export_path_target_that_is_a_file_is_422_named(tmp_path: Path) -> None:
    """An existing file is not an export target: the truth is "is a file", 422."""
    target = tmp_path / "already-here"
    target.write_bytes(b"not a directory yet")
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")

        response = await client.post(
            f"/api/writing/novels/{novel_id}/export",
            json={"mode": "path", "path": str(target)},
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert ["body", "path"] in [entry["loc"] for entry in detail]
        assert "is a file" in detail[0]["msg"]
        # The file is untouched: a refusal writes nothing.
        assert target.read_bytes() == b"not a directory yet"


async def test_import_zip_as_new_novel() -> None:
    """An uploaded ZIP becomes a new novel; the report counts what it made."""
    data = _archive_zip("Der Import")
    async with _client() as client:
        response = await client.post(
            "/api/writing/novels/import", files={"archive": ("der-import.zip", data)}
        )
        assert response.status_code == 201
        report = response.json()
        # The exact shape the web client consumes — no more, no less.
        assert set(report) == {
            "novel_id",
            "chapters_new",
            "chapters_revised",
            "chapters_already_current",
            "entities_new",
            "entities_revised",
            "entities_renamed",
            "entities_already_current",
            "relations_created",
            "relations_already_current",
            "conflicts",
            "metadata_conflicts",
        }
        novel_id = UUID(report["novel_id"])
        assert report["chapters_new"] == 1
        assert report["entities_new"] == 1
        assert report["conflicts"] == []
        assert report["metadata_conflicts"] == []

        # Real state, through the API: the novel, its chapter, its entity exist.
        novel = await client.get(f"/api/writing/novels/{novel_id}")
        assert novel.status_code == 200
        assert novel.json()["title"] == "Der Import"
        chapters = await client.get(f"/api/writing/novels/{novel_id}/chapters")
        assert [chapter["title"] for chapter in chapters.json()] == ["Kapitel eins"]
        entities = await client.get(f"/api/knowledge/novels/{novel_id}/entities")
        assert [entity["name"] for entity in entities.json()] == ["Vega"]


async def test_import_path_merge_into_existing(tmp_path: Path) -> None:
    """A path import into an existing novel merges; report counts match the DB."""
    export = tmp_path / "export"
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel", chapter="Erstes Kapitel")
        written = await client.post(
            f"/api/writing/novels/{novel_id}/export", json={"mode": "path", "path": str(export)}
        )
        assert written.status_code == 200

        merged = await client.post(
            "/api/writing/novels/import",
            data={"path": str(export), "novel_id": str(novel_id)},
        )
        assert merged.status_code == 201
        report = merged.json()
        assert UUID(report["novel_id"]) == novel_id
        assert report["chapters_already_current"] == 1
        assert report["chapters_new"] == 0
        assert report["conflicts"] == []
        assert report["metadata_conflicts"] == []

        # Merged, not duplicated: the DB still carries exactly the one chapter.
        chapters = await client.get(f"/api/writing/novels/{novel_id}/chapters")
        assert [chapter["title"] for chapter in chapters.json()] == ["Erstes Kapitel"]


async def test_imports_of_one_book_at_once_take_distinct_numbers() -> None:
    """Two imports landing together each get their own chapter number.

    The importer allocates the append slot itself; without the same lock the
    creation path takes, both read one max and the second import dies on the
    unique position (#521).
    """
    data = zip_bytes(
        serialize_archive(
            NovelArchive(
                title="Der Nebel",
                chapters=[ChapterFile(title="Kapitel eins", position=0, body="Der Anfang.\n")],
                entities=[],
            )
        )
    )

    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")

    async def one_import() -> int:
        async with _client() as client:
            response = await client.post(
                "/api/writing/novels/import",
                files={"archive": ("der-import.zip", data)},
                data={"novel_id": str(novel_id)},
            )
            return response.status_code

    codes = await asyncio.gather(*(one_import() for _ in range(4)))
    assert codes == [201] * 4

    async with _client() as client:
        listed = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()
    assert [chapter["position"] for chapter in listed] == [0, 1, 2, 3]


async def test_import_needs_exactly_one_source() -> None:
    """Neither or both of archive/path is a 422 naming the fields."""
    async with _client() as client:
        neither = await client.post("/api/writing/novels/import", data={"novel_id": str(uuid4())})
        assert neither.status_code == 422
        fields = [entry["loc"] for entry in neither.json()["detail"]]
        assert ["body", "archive"] in fields
        assert ["body", "path"] in fields

        both = await client.post(
            "/api/writing/novels/import",
            files={"archive": ("x.zip", _archive_zip("Der Import"))},
            data={"path": "/somewhere"},
        )
        assert both.status_code == 422
        fields = [entry["loc"] for entry in both.json()["detail"]]
        assert ["body", "archive"] in fields
        assert ["body", "path"] in fields


async def test_oversized_zip_is_413() -> None:
    """One byte over MAX_ARCHIVE_BYTES is refused before it is parsed."""
    from app.capabilities.writing.service import MAX_ARCHIVE_BYTES

    data = b"x" * (MAX_ARCHIVE_BYTES + 1)
    async with _client() as client:
        response = await client.post(
            "/api/writing/novels/import", files={"archive": ("big.zip", data)}
        )
        assert response.status_code == 413
        assert response.json() == {"detail": "archive too large"}


async def test_oversized_zip_is_refused_before_it_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The route checks the upload's size, so an oversized body never lands in
    memory; the service check stays the authority behind it."""
    from app.capabilities.writing.service import MAX_ARCHIVE_BYTES

    async def never_read(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("the oversized upload was read into memory")

    monkeypatch.setattr(UploadFile, "read", never_read)
    data = b"x" * (MAX_ARCHIVE_BYTES + 1)
    async with _client() as client:
        response = await client.post(
            "/api/writing/novels/import", files={"archive": ("big.zip", data)}
        )
        assert response.status_code == 413
        assert response.json() == {"detail": "archive too large"}


async def test_malformed_archive_is_422_with_file_named() -> None:
    """A ZIP whose metadata.json is not JSON is a 422 naming the file."""
    data = zip_bytes({"metadata.json": b"{ definitely not json"})
    async with _client() as client:
        response = await client.post(
            "/api/writing/novels/import", files={"archive": ("broken.zip", data)}
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["file"] == "metadata.json"
        assert detail["reason"]


async def test_encrypted_archive_is_422_with_file_named() -> None:
    """An encrypted entry raises RuntimeError at read, not BadZipFile; it is a
    refusal naming the archive, never a 500."""
    async with _client() as client:
        response = await client.post(
            "/api/writing/novels/import", files={"archive": ("locked.zip", _encrypted_zip())}
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "archive_invalid"
        assert detail["file"] == "<archive>"
        assert "encrypted" in detail["reason"].lower()


async def test_corrupted_archive_payload_is_422_with_file_named() -> None:
    """A damaged deflate stream raises zlib.error at read; it is the archive's
    fault, named in the 422 — never an unhandled 500 the UI reads as an outage."""
    async with _client() as client:
        response = await client.post(
            "/api/writing/novels/import", files={"archive": ("corrupt.zip", _corrupted_zip())}
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "archive_invalid"
        assert detail["file"] == "<archive>"
        assert detail["reason"]


async def test_import_path_source_unreachable_is_422_named(tmp_path: Path) -> None:
    """A server-side path that is not there is a 422 naming `path`, with the
    OS reason — not a 500 and not a 404."""
    async with _client() as client:
        response = await client.post(
            "/api/writing/novels/import", data={"path": str(tmp_path / "missing")}
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert ["body", "path"] in [entry["loc"] for entry in detail]
        assert "is not a directory" in detail[0]["msg"]


async def test_import_new_novel_without_the_setup_user_is_409_and_writes_nothing() -> None:
    """A new-novel import writes rows owned by a user; on an instance setup
    has not created, it answers the create route's 409 and writes nothing."""
    async with Session() as session:
        await session.execute(delete(User).where(User.id == LOCAL_USER_ID))
        await session.commit()

    async with _client() as client:
        response = await client.post(
            "/api/writing/novels/import",
            files={"archive": ("der-import.zip", _archive_zip("Der Import"))},
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "setup required"}
        # The refused import committed nothing: no novel on the shelf.
        assert (await client.get("/api/writing/novels")).json() == []


async def test_import_into_foreign_novel_is_404() -> None:
    """Merging into another user's novel is the same answer as a missing one."""
    await seed_user(OTHER_USER)
    async with Session() as session:
        foreign = Novel(user_id=OTHER_USER, title="Fremd")
        session.add(foreign)
        await session.commit()
        foreign_id = foreign.id

    async with _client() as client:
        response = await client.post(
            "/api/writing/novels/import",
            files={"archive": ("der-import.zip", _archive_zip("Der Import"))},
            data={"novel_id": str(foreign_id)},
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "novel not found"}


async def test_import_reports_conflicts_with_file_and_reason() -> None:
    """A refused item is a conflict row naming its archive file and why."""
    archive = NovelArchive(
        title="Mit Konflikt",
        entities=[EntityFile(name="Drache", type="dragon", aliases=[], tags=[], body="Zu groß.\n")],
    )
    async with _client() as client:
        response = await client.post(
            "/api/writing/novels/import",
            files={"archive": ("konflikt.zip", zip_bytes(serialize_archive(archive)))},
        )
        assert response.status_code == 201
        report = response.json()
        assert report["entities_new"] == 0
        assert len(report["conflicts"]) == 1
        conflict = report["conflicts"][0]
        assert set(conflict) == {"file", "reason", "code", "params"}
        assert conflict["file"] == "kb/drache.md"
        assert conflict["code"] == "unknown_type"
        assert conflict["params"] == {"type": "dragon"}
        assert "unknown entity type 'dragon'" in conflict["reason"]

        # The refused item was not created: the novel has no entity.
        novel_id = UUID(report["novel_id"])
        entities = await client.get(f"/api/knowledge/novels/{novel_id}/entities")
        assert entities.json() == []


async def test_export_path_mode_needs_a_path() -> None:
    """mode=path without a target path is a 422 naming the field."""
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")

        response = await client.post(
            f"/api/writing/novels/{novel_id}/export", json={"mode": "path"}
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert ["body", "path"] in [entry["loc"] for entry in detail]


async def test_foreign_novel_is_404() -> None:
    """Exporting another user's novel id is the same answer as a missing one —
    proven against a same-shaped novel the local user does own."""
    await seed_user(OTHER_USER)
    async with Session() as session:
        foreign = Novel(user_id=OTHER_USER, title="Fremd")
        session.add(foreign)
        await session.commit()
        foreign_id = foreign.id

    async with _client() as client:
        own_id = await _create_novel(client, "Fremd")
        own = await client.post(f"/api/writing/novels/{own_id}/export", json={"mode": "zip"})
        assert own.status_code == 200

        response = await client.post(
            f"/api/writing/novels/{foreign_id}/export", json={"mode": "zip"}
        )
        assert response.status_code == 404
