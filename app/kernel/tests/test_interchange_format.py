"""The interchange format's contract: one archive, two transports, no drift.

These tests pin what Tasks 3-5 build on: the round trip out of and back into
the format is byte-identical, a directory and a ZIP of the same files parse
into the same archive, bare hand-written Markdown falls back to documented
defaults, malformed frontmatter names the offending file, serialization is
deterministic (slug rule, zero-padded positions, `metadata.json` first), and
relations ride `metadata.json` as `from`/`type`/`to`/`note?`.
"""

import io
import json
import struct
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from app.kernel.interchange import (
    ArchiveError,
    ChapterFile,
    EntityFile,
    NovelArchive,
    RelationEdge,
    open_directory,
    open_zip,
    parse_archive,
    serialize_archive,
    write_directory,
    zip_bytes,
)
from app.kernel.interchange.tree import MAX_UNCOMPRESSED_BYTES

_CHAPTER_ID = UUID("0f0e8d4a-7b3c-4d5e-8f90-1a2b3c4d5e6f")
_ENTITY_ID = UUID("a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")
_UPDATED = datetime(2026, 1, 15, 12, 30, tzinfo=UTC)


def _archive() -> NovelArchive:
    """A small but complete archive: unicode, colons, ids, notes, empty lists.

    `file` and `indexed_position` ride on chapters and entities because the
    round trip below compares a *parsed* archive: parse stamps the paths it
    read from and the index positions the metadata lent, and serialize must
    forget both again (byte-identical files, no provenance in the format).
    """
    return NovelArchive(
        title="Der Wanderer",
        author="E. A. Guest",
        genre="Fantasy",
        blurb="Ein Roman über Wege.",
        language="de",
        chapters=[
            ChapterFile(
                title="Ankunft: Am Tor",
                position=1,
                body="Der Regen hörte auf.\n",
                id=_CHAPTER_ID,
                updated=_UPDATED,
                file="chapters/01-ankunft-am-tor.md",
                indexed_position=1,
            ),
            ChapterFile(
                title="Der Pfad",
                position=2,
                body="Zweiter Teil ohne id.",
                file="chapters/02-der-pfad.md",
                indexed_position=2,
            ),
            ChapterFile(
                title="",
                position=3,
                body="Ohne Titel.\n",
                file="chapters/03-untitled.md",
                indexed_position=3,
            ),
        ],
        # Parse returns entities in kb-filename order: emile-zola, mira, untitled.
        entities=[
            EntityFile(
                name="Émile Zola",
                type="character",
                aliases=[],
                tags=[],
                body="Schriftsteller.",
                id=_ENTITY_ID,
                updated=_UPDATED,
                file="kb/emile-zola.md",
            ),
            EntityFile(
                name="Mira",
                type="character",
                aliases=["Die Wanderin"],
                tags=["protagonist"],
                body="## Beschreibung\nJung.\n",
                file="kb/mira.md",
            ),
            EntityFile(
                name="",
                type="",
                aliases=[],
                tags=[],
                body="Ohne Namen.",
                file="kb/untitled.md",
            ),
        ],
        relations=[
            RelationEdge(
                from_name="Mira", relation_type="knows", to_name="Émile Zola", note="aus Briefen"
            ),
            RelationEdge(from_name="Émile Zola", relation_type="mentors", to_name="Mira"),
        ],
    )


def test_round_trip_is_byte_identical(tmp_path: Path) -> None:
    """Write, read back, serialize again: same bytes, same archive."""
    files = serialize_archive(_archive())
    target = tmp_path / "archive"
    write_directory(target, files)

    parsed = parse_archive(open_directory(target))
    assert parsed == _archive()

    files_again = serialize_archive(parsed)
    assert files_again == files
    assert next(iter(files_again)) == "metadata.json"


def test_zip_and_directory_parse_identically(tmp_path: Path) -> None:
    """The transport is invisible: ZIP bytes and a directory parse the same."""
    files = serialize_archive(_archive())
    assert zip_bytes(files) == zip_bytes(files)

    write_directory(tmp_path / "dir", files)
    from_directory = parse_archive(open_directory(tmp_path / "dir"))
    from_zip = parse_archive(open_zip(zip_bytes(files)))
    assert from_zip == from_directory


def test_bare_md_without_frontmatter_uses_defaults() -> None:
    """A hand-dropped file needs nothing: stem as title, appearance order, generic."""
    files = {
        "chapters/the-quest.md": b"Ein Kapitel ohne Frontmatter.\n",
        "kb/wizard.md": b"## Beschreibung\nEin alter Zauberer.\n",
    }

    parsed = parse_archive(open_zip(zip_bytes(files)))

    assert parsed.title == ""
    assert parsed.author is None and parsed.genre is None
    assert parsed.blurb is None and parsed.language is None
    assert parsed.relations == []
    assert parsed.chapters == [
        ChapterFile(
            title="the quest",
            position=1,
            body="Ein Kapitel ohne Frontmatter.\n",
            file="chapters/the-quest.md",
            # No metadata.json, no index: the position rides on appearance.
            indexed_position=None,
        )
    ]
    assert parsed.entities == [
        EntityFile(
            name="wizard",
            type="generic",
            aliases=[],
            tags=[],
            body="## Beschreibung\nEin alter Zauberer.\n",
            file="kb/wizard.md",
        )
    ]


def test_metadata_index_lends_its_position() -> None:
    """A file without a frontmatter position takes the index's; with one, the
    frontmatter wins and the disagreement is visible as provenance."""
    files = {
        "metadata.json": (
            b'{"title": "X", "chapters": ['
            b'{"file": "chapters/indexed.md", "position": 4},'
            b'{"file": "chapters/disputed.md", "position": 4}]}'
        ),
        "chapters/indexed.md": b"Kein Frontmatter-Position.\n",
        "chapters/disputed.md": b"---\ntitle: Disputed\nposition: 9\n---\n\nNeun.\n",
    }

    parsed = parse_archive(open_zip(zip_bytes(files)))

    indexed = next(c for c in parsed.chapters if c.title == "indexed")
    assert indexed.position == 4  # the index lent it; appearance would say 2
    assert indexed.indexed_position == 4
    disputed = next(c for c in parsed.chapters if c.title == "Disputed")
    assert disputed.position == 9  # the frontmatter wins for placement
    assert disputed.indexed_position == 4  # the disagreement is visible to the engine
    assert parsed.chapters == sorted(parsed.chapters, key=lambda c: (c.position, c.file or ""))


def test_malformed_frontmatter_names_the_file() -> None:
    """Bad YAML refuses the parse and the message carries the relpath."""
    files = {
        "metadata.json": b'{"title": "X"}',
        "chapters/01-x.md": b"---\ntitle: [unclosed\n---\nKapitel.\n",
    }

    with pytest.raises(ArchiveError) as raised:
        parse_archive(open_zip(zip_bytes(files)))

    assert raised.value.path == "chapters/01-x.md"
    assert "chapters/01-x.md" in str(raised.value)


def test_directory_reads_only_the_format_surface(tmp_path: Path) -> None:
    """A directory is not a filesystem walk: the format's three groups are the
    archive, and everything beside them (a checkout, a binary, a stray note)
    is never opened — typing `.` must not read the whole repository."""
    target = tmp_path / "archive"
    (target / "chapters").mkdir(parents=True)
    (target / "kb").mkdir()
    (target / "metadata.json").write_text('{"title": "Der Wanderer"}', encoding="utf-8")
    (target / "chapters" / "01-start.md").write_text("Der Anfang.\n", encoding="utf-8")
    (target / "kb" / "mira.md").write_text("Mira.\n", encoding="utf-8")
    # Foreign files, one of them invalid UTF-8: reading it would refuse a parse
    # of a perfectly good archive.
    (target / ".venv" / "lib").mkdir(parents=True)
    (target / ".venv" / "lib" / "huge.py").write_bytes(b"\xff" * 4096)
    (target / "notes.txt").write_text("not part of the archive", encoding="utf-8")
    (target / "kb" / "notes.txt").write_bytes(b"\xff\xfe not markdown")

    tree = open_directory(target)
    parsed = parse_archive(tree)

    # The tree itself is the contract: an `rglob("*")` reader parses the same
    # archive and would pass the assertions below, so the foreign paths must
    # be absent from the tree, not merely ignored by the parser.
    with pytest.raises(FileNotFoundError):
        tree.read_bytes(".venv/lib/huge.py")
    with pytest.raises(FileNotFoundError):
        tree.read_bytes("notes.txt")

    assert parsed.title == "Der Wanderer"
    assert [chapter.file for chapter in parsed.chapters] == ["chapters/01-start.md"]
    assert [entity.file for entity in parsed.entities] == ["kb/mira.md"]


def test_zip_claiming_more_than_the_uncompressed_cap_is_refused_named() -> None:
    """A ZIP whose entry claims to expand past the cap refuses before it is
    read — the compressed upload cap does not bound what `read()` would hold."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as bundle:
        bundle.writestr(zipfile.ZipInfo("metadata.json"), b"{}")
    data = bytearray(buffer.getvalue())
    for signature, offset in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
        struct.pack_into("<I", data, data.find(signature) + offset, MAX_UNCOMPRESSED_BYTES + 1)

    with pytest.raises(ArchiveError) as raised:
        open_zip(bytes(data))

    assert raised.value.path == "metadata.json"
    assert str(MAX_UNCOMPRESSED_BYTES) in raised.value.reason


def test_directory_over_the_uncompressed_cap_is_refused_named(tmp_path: Path) -> None:
    """A directory whose files total past the cap refuses, naming the path."""
    target = tmp_path / "archive"
    (target / "chapters").mkdir(parents=True)
    (target / "metadata.json").write_text('{"title": "X"}', encoding="utf-8")
    with (target / "chapters" / "01-big.md").open("wb") as handle:
        handle.truncate(MAX_UNCOMPRESSED_BYTES + 1)  # sparse: the size is what counts

    with pytest.raises(ArchiveError) as raised:
        open_directory(target)

    assert raised.value.path == str(target)
    assert str(MAX_UNCOMPRESSED_BYTES) in raised.value.reason


def test_over_long_metadata_title_is_refused_by_name() -> None:
    """A field wider than its column refuses at parse, naming field and limit —
    never a database error halfway through the import."""
    files = {
        "metadata.json": json.dumps({"title": "x" * 201}).encode(),
        "chapters/a.md": b"Text.\n",
    }

    with pytest.raises(ArchiveError) as raised:
        parse_archive(open_zip(zip_bytes(files)))

    assert raised.value.path == "metadata.json"
    assert "title" in raised.value.reason
    assert "200" in raised.value.reason


def test_over_long_chapter_title_is_refused_by_name() -> None:
    """A chapter title past the column width is the same named refusal, and it
    names the chapter file that carries it."""
    files = {
        "metadata.json": b'{"title": "X"}',
        "chapters/01-lang.md": ("---\ntitle: " + "x" * 201 + "\n---\n\nText.\n").encode(),
    }

    with pytest.raises(ArchiveError) as raised:
        parse_archive(open_zip(zip_bytes(files)))

    assert raised.value.path == "chapters/01-lang.md"
    assert "title" in raised.value.reason
    assert "200" in raised.value.reason


def test_over_long_relation_type_is_refused_by_name() -> None:
    """A relation type wider than its column refuses, naming the relation."""
    files = {
        "metadata.json": json.dumps(
            {"title": "X", "relations": [{"from": "A", "type": "t" * 81, "to": "B"}]}
        ).encode(),
    }

    with pytest.raises(ArchiveError) as raised:
        parse_archive(open_zip(zip_bytes(files)))

    assert raised.value.path == "metadata.json"
    assert "relation #1" in raised.value.reason
    assert "80" in raised.value.reason


def test_serialize_is_deterministic() -> None:
    """Twice the same archive, twice the same bytes; slug and padding pinned."""
    first = serialize_archive(_archive())
    second = serialize_archive(_archive())
    assert first == second
    assert next(iter(first)) == "metadata.json"
    assert set(first) == {
        "metadata.json",
        "chapters/01-ankunft-am-tor.md",
        "chapters/02-der-pfad.md",
        "chapters/03-untitled.md",  # an empty title exports the untitled slug
        "kb/emile-zola.md",
        "kb/mira.md",
        "kb/untitled.md",
    }

    pinned = serialize_archive(
        NovelArchive(
            title="S",
            chapters=[
                ChapterFile(title="Kapitel 7!", position=7, body=""),
                ChapterFile(title="", position=12, body=""),
            ],
            entities=[
                EntityFile(name="Anna", type="generic", aliases=[], tags=[], body=""),
                EntityFile(name="ANNA", type="generic", aliases=[], tags=[], body=""),
                EntityFile(name="", type="generic", aliases=[], tags=[], body=""),
            ],
        )
    )
    assert set(pinned) == {
        "metadata.json",
        "chapters/07-kapitel-7.md",  # <nn> is the zero-padded position
        "chapters/12-untitled.md",  # empty title slugs to untitled
        "kb/anna.md",
        "kb/anna-2.md",  # ASCII-folding ANNA collides with Anna -> -2
        "kb/untitled.md",
    }


def test_slug_collision_assignment_is_order_free() -> None:
    """Which same-slug name keeps the bare slug is a pure function of the names.

    "ANNA" sorts before "Anna", so ANNA rides `anna.md` regardless of list
    order — and because parse returns entities in file-name order, the
    re-serialization is a fixed point instead of swapping the two files.
    """
    files = serialize_archive(
        NovelArchive(
            title="S",
            entities=[
                EntityFile(name="Anna", type="generic", aliases=[], tags=[], body="Die Erste."),
                EntityFile(name="ANNA", type="generic", aliases=[], tags=[], body="Die Zweite."),
            ],
        )
    )
    swapped = serialize_archive(
        NovelArchive(
            title="S",
            entities=[
                EntityFile(name="ANNA", type="generic", aliases=[], tags=[], body="Die Zweite."),
                EntityFile(name="Anna", type="generic", aliases=[], tags=[], body="Die Erste."),
            ],
        )
    )
    assert files == swapped
    assert set(files) == {"metadata.json", "kb/anna.md", "kb/anna-2.md"}
    assert (
        files["kb/anna.md"]
        == serialize_archive(
            NovelArchive(
                title="S",
                entities=[
                    EntityFile(name="ANNA", type="generic", aliases=[], tags=[], body="Die Zweite.")
                ],
            )
        )["kb/anna.md"]
    )

    again = serialize_archive(parse_archive(open_zip(zip_bytes(files))))
    assert again == files


def test_metadata_json_relations_parse() -> None:
    """Relations round-trip through metadata.json as from/type/to/note?."""
    files = serialize_archive(_archive())
    metadata = json.loads(files["metadata.json"])
    assert metadata == {
        "title": "Der Wanderer",
        "author": "E. A. Guest",
        "genre": "Fantasy",
        "blurb": "Ein Roman über Wege.",
        "language": "de",
        "chapters": [
            {"file": "chapters/01-ankunft-am-tor.md", "position": 1},
            {"file": "chapters/02-der-pfad.md", "position": 2},
            {"file": "chapters/03-untitled.md", "position": 3},
        ],
        "relations": [
            {"from": "Mira", "type": "knows", "to": "Émile Zola", "note": "aus Briefen"},
            {"from": "Émile Zola", "type": "mentors", "to": "Mira"},  # no note key
        ],
    }

    parsed = parse_archive(open_zip(zip_bytes(files)))
    assert parsed.relations == _archive().relations


def test_write_failure_leaves_no_partial_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write that dies mid-loop leaves no target for the retry to trip on.

    The originals: a full disk (ENOSPC) or a permission change (EACCES) part
    way through. Nothing of the half-written tree may survive, or the retry
    would meet its own debris as `target not empty`.
    """
    files = {
        "metadata.json": b'{"title": "X"}',
        "chapters/00-erstes-kapitel.md": b"Der Anfang.\n",
    }
    real_write = Path.write_bytes

    def die_on_the_chapter(self: Path, data: bytes) -> int:
        if self.name == "00-erstes-kapitel.md":
            raise OSError(28, "No space left on device")
        return real_write(self, data)

    monkeypatch.setattr(Path, "write_bytes", die_on_the_chapter)
    target = tmp_path / "export"

    with pytest.raises(OSError):
        write_directory(target, files)

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []  # nor a staging directory


def test_write_into_an_existing_empty_target_succeeds(tmp_path: Path) -> None:
    """The atomic rename may replace an empty directory, the one non-empty refuses."""
    target = tmp_path / "export"
    target.mkdir()
    files = {"metadata.json": b"{}"}

    write_directory(target, files)

    assert (target / "metadata.json").read_bytes() == b"{}"
    assert list(tmp_path.iterdir()) == [target]
