"""The interchange format's contract: one archive, two transports, no drift.

These tests pin what Tasks 3-5 build on: the round trip out of and back into
the format is byte-identical, a directory and a ZIP of the same files parse
into the same archive, bare hand-written Markdown falls back to documented
defaults, malformed frontmatter names the offending file, serialization is
deterministic (slug rule, zero-padded positions, `metadata.json` first), and
relations ride `metadata.json` as `from`/`type`/`to`/`note?`.
"""

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
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

if TYPE_CHECKING:
    from pathlib import Path

_CHAPTER_ID = UUID("0f0e8d4a-7b3c-4d5e-8f90-1a2b3c4d5e6f")
_ENTITY_ID = UUID("a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")
_UPDATED = datetime(2026, 1, 15, 12, 30, tzinfo=UTC)


def _archive() -> NovelArchive:
    """A small but complete archive: unicode, colons, ids, notes, empty lists."""
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
            ),
            ChapterFile(title="Der Pfad", position=2, body="Zweiter Teil ohne id."),
        ],
        # Parse returns entities in kb-filename order: emile-zola before mira.
        entities=[
            EntityFile(
                name="Émile Zola",
                type="character",
                aliases=[],
                tags=[],
                body="Schriftsteller.",
                id=_ENTITY_ID,
                updated=_UPDATED,
            ),
            EntityFile(
                name="Mira",
                type="character",
                aliases=["Die Wanderin"],
                tags=["protagonist"],
                body="## Beschreibung\nJung.\n",
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
        ChapterFile(title="the quest", position=1, body="Ein Kapitel ohne Frontmatter.\n")
    ]
    assert parsed.entities == [
        EntityFile(
            name="wizard",
            type="generic",
            aliases=[],
            tags=[],
            body="## Beschreibung\nEin alter Zauberer.\n",
        )
    ]


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
        "kb/emile-zola.md",
        "kb/mira.md",
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
        ],
        "relations": [
            {"from": "Mira", "type": "knows", "to": "Émile Zola", "note": "aus Briefen"},
            {"from": "Émile Zola", "type": "mentors", "to": "Mira"},  # no note key
        ],
    }

    parsed = parse_archive(open_zip(zip_bytes(files)))
    assert parsed.relations == _archive().relations
