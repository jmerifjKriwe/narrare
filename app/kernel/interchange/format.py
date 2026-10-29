"""The interchange format itself: the archive dataclasses, the parser, the serializer.

One novel is one directory (or one ZIP of the same bytes):

    novel/
      metadata.json      { title, author?, genre?, blurb?, language?,
                           chapters: [{file, position}],            # ordered index
                           relations: [{from, type, to, note?}] }   # names, not ids
      chapters/<nn>-<slug>.md   frontmatter: title, position, id?, updated?
      kb/<slug>.md              frontmatter: type, name, aliases[], tags[], id?, updated?

This module is pure parsing and serialization — no database, no merge rules
(those live in the engine). Everything is deterministic so that exporting an
archive twice, or exporting what was just parsed, yields byte-identical files:
frontmatter keys ride in a fixed order through `yaml.safe_dump`
(`sort_keys=False`), lists keep their order, `metadata.json` sorts its keys in
writing order, file names are slugs with a numeric suffix on collision and a
zero-padded position prefix on chapters.

Frontmatter parsing is strict where lying would corrupt a novel (a non-string
title, a non-integer position, a present-but-blank entity name or type, a
blank relation type) and forgiving where a hand-written file can
simply omit things: a file without frontmatter parses with defaults — the
chapter title from the de-slugged filename stem, the position from the order
of appearance (the metadata index wins over appearance, frontmatter over the
index), the entity type `generic`, empty alias and tag lists. Everything
malformed raises `ArchiveError` with the offending file named.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import yaml

if TYPE_CHECKING:
    from app.kernel.interchange.tree import ArchiveTree

METADATA_NAME = "metadata.json"
"""The one index file every archive carries; absent means a bare file drop."""

_YAML_WIDTH = 10**6
"""No line wrapping: the frontmatter is a data file, not prose."""

_MAX_LENGTHS: dict[str, int] = {
    # The column widths the archive writes into. Validated at parse, so a
    # hostile or careless file is a named 422 instead of a database error
    # halfway through the import's one transaction.
    "title": 200,  # novels.title, chapters.title
    "author": 200,  # novels.author
    "genre": 80,  # novels.genre
    "language": 16,  # novels.language
    "name": 200,  # entities.name
    "relation_type": 80,  # entity_relations.relation_type
}
"""The longest a value may be, per semantic field — the database's own widths."""


class ArchiveError(Exception):
    """A malformed archive: the offending file (or path) and the reason."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


@dataclass
class ChapterFile:
    """One chapter as the format holds it: frontmatter plus body.

    `file` and `indexed_position` are parse provenance, not serialized
    format: the archive-relative path the chapter was read from (None on a
    file constructed in code), and the position `metadata.json`'s index lent
    it (None when the index does not name the file). `position` is the
    effective one — the frontmatter's when present — so a disagreement
    between the two is visible here and is the merge engine's reported
    conflict; the frontmatter still wins for placement.
    """

    title: str
    position: int
    body: str
    id: UUID | None = None
    updated: datetime | None = None
    file: str | None = None
    indexed_position: int | None = None


@dataclass
class EntityFile:
    """One knowledge-base entry as the format holds it.

    `file` is parse provenance, not serialized format: the archive-relative
    path the entry was read from, None on a file constructed in code.
    """

    name: str
    type: str
    aliases: list[str]
    tags: list[str]
    body: str
    id: UUID | None = None
    updated: datetime | None = None
    file: str | None = None


@dataclass
class RelationEdge:
    """One edge of `metadata.json`; both ends are entity names, not ids."""

    from_name: str
    relation_type: str
    to_name: str
    note: str | None = None


@dataclass
class NovelArchive:
    """A whole novel in the interchange format, ready to parse or serialize.

    `title` is empty when `metadata.json` is absent or carries none — the
    new-novel import path refuses an empty title, the merge path never
    applies novel metadata.
    """

    title: str
    author: str | None = None
    genre: str | None = None
    blurb: str | None = None
    language: str | None = None
    chapters: list[ChapterFile] = field(default_factory=list[ChapterFile])
    entities: list[EntityFile] = field(default_factory=list[EntityFile])
    relations: list[RelationEdge] = field(default_factory=list[RelationEdge])


# ---------------------------------------------------------------------------
# Names: slug rule and its inverse for bare files
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Lowercase, ASCII-folded, non-alphanumerics to `-`, trimmed; empty -> untitled."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower())
    return slug.strip("-") or "untitled"


def _check_length(value: str, relpath: str, field: str, limit: int, label: str = "") -> None:
    """Refuse a value wider than its column, naming the field and the limit."""
    if len(value) > limit:
        prefix = f"{label}: " if label else ""
        raise ArchiveError(
            relpath,
            f"{prefix}'{field}' is {len(value)} characters — the format allows {limit}",
        )


def _check_non_blank(value: str, relpath: str, field: str, label: str = "") -> None:
    """Refuse a value that is present but empty or only whitespace, naming
    the field.

    Omission defaults (untitled chapter, stem-named entity, `generic` type);
    an explicit blank is a value the database would carry as an unusable row
    — a nameless entity has nothing relations can point at, a typeless one
    has no type to resolve. Refused at parse, like the length caps."""
    if not value.strip():
        prefix = f"{label}: " if label else ""
        raise ArchiveError(relpath, f"{prefix}'{field}' is blank")


def _assign_slugs[K](keys: list[tuple[K, ...]]) -> list[str]:
    """A slug per entry key; collisions are suffixed in sorted-key order.

    Which same-slug name keeps the bare slug is a pure function of the key
    set, never of list arrival: whichever entry sorts first wins `slug`, the
    next wins `slug-2`, and so on. Serialize→parse→serialize is therefore a
    fixed point (parse returns entities in file-name order, and
    `anna-2.md` sorts before `anna.md`), and a swapped input list produces
    the same files.
    """
    order = sorted(range(len(keys)), key=keys.__getitem__)
    slugs: list[str] = [""] * len(keys)
    taken: set[str] = set()
    for index in order:
        base = str(keys[index][0])
        candidate = base
        suffix = 2
        while candidate in taken:
            candidate = f"{base}-{suffix}"
            suffix += 1
        taken.add(candidate)
        slugs[index] = candidate
    return slugs


def _deslug(stem: str) -> str:
    """The inverse for bare files: hyphens become spaces, whitespace collapses."""
    title = re.sub(r"\s+", " ", stem.replace("-", " ")).strip()
    return title or "untitled"


def _stem(relpath: str) -> str:
    return relpath.rsplit("/", 1)[-1].removesuffix(".md")


# ---------------------------------------------------------------------------
# Frontmatter: split, load, dump
# ---------------------------------------------------------------------------


def _split_frontmatter(text: str, relpath: str) -> tuple[dict[str, Any], str]:
    """YAML between `---` lines, or the whole text as body; malformed YAML refuses."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return {}, text  # no frontmatter — not even a stray thematic break harmed
    closing = next(
        (index for index in range(1, len(lines)) if lines[index].rstrip("\r\n") == "---"),
        None,
    )
    if closing is None:
        return {}, text  # a `---` first line without a closer is prose, not frontmatter
    try:
        document = yaml.safe_load("".join(lines[1:closing]))
    except yaml.YAMLError as error:
        raise ArchiveError(relpath, f"invalid frontmatter YAML: {error}") from error
    mapping: dict[str, Any]
    if document is None:
        mapping = {}
    elif isinstance(document, dict):
        mapping = cast("dict[str, Any]", document)
    else:
        raise ArchiveError(relpath, "frontmatter is not a mapping")
    return mapping, "".join(lines[closing + 1 :]).lstrip("\r\n")


def _dump_frontmatter(mapping: dict[str, Any]) -> str:
    """Deterministic YAML: insertion order, no wrapping, unicode literal."""
    return yaml.safe_dump(mapping, sort_keys=False, allow_unicode=True, width=_YAML_WIDTH)


def _file_bytes(frontmatter: str, body: str) -> bytes:
    """One Markdown file: frontmatter block, one blank line, the body as-is."""
    text = f"---\n{frontmatter}---\n"
    if body:
        text += f"\n{body}"
    return text.encode("utf-8")


# ---------------------------------------------------------------------------
# Frontmatter field coercion — every failure names the file
# ---------------------------------------------------------------------------


def _fm_str(frontmatter: dict[str, Any], key: str, relpath: str) -> str | None:
    """The value, or None when the key is absent or explicitly null.

    An empty string is a value and is returned as one: callers decide by
    presence, never by truthiness.
    """
    value = frontmatter.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ArchiveError(relpath, f"'{key}' is not a string")
    return value


def _fm_int(frontmatter: dict[str, Any], key: str, relpath: str, fallback: int) -> int:
    value = frontmatter.get(key)
    if value is None:
        return fallback
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ArchiveError(relpath, f"'{key}' is not an integer")
    try:
        return int(value)
    except ValueError as error:
        raise ArchiveError(relpath, f"'{key}' is not an integer") from error


def _fm_uuid(frontmatter: dict[str, Any], key: str, relpath: str) -> UUID | None:
    value = frontmatter.get(key)
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as error:
            raise ArchiveError(relpath, f"'{key}' is not a UUID") from error
    raise ArchiveError(relpath, f"'{key}' is not a UUID")


def _fm_datetime(frontmatter: dict[str, Any], key: str, relpath: str) -> datetime | None:
    value = frontmatter.get(key)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as error:
            raise ArchiveError(relpath, f"'{key}' is not an ISO-8601 timestamp") from error
    raise ArchiveError(relpath, f"'{key}' is not an ISO-8601 timestamp")


def _fm_str_list(frontmatter: dict[str, Any], key: str, relpath: str) -> list[str]:
    value = frontmatter.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ArchiveError(relpath, f"'{key}' is not a list")
    items: list[str] = []
    for entry in cast("list[object]", value):
        if not isinstance(entry, str):
            raise ArchiveError(relpath, f"'{key}' contains a value that is not a string")
        items.append(entry)
    return items


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def parse_archive(tree: ArchiveTree) -> NovelArchive:
    """Read the abstract tree into a `NovelArchive`; malformed files refuse by name."""
    metadata = _read_metadata(tree)
    return NovelArchive(
        title=_meta_str(metadata, "title") or "",
        author=_meta_str(metadata, "author"),
        genre=_meta_str(metadata, "genre"),
        blurb=_meta_str(metadata, "blurb"),
        language=_meta_str(metadata, "language"),
        chapters=_parse_chapters(tree, metadata),
        entities=_parse_entities(tree),
        relations=_parse_relations(metadata),
    )


def _read_metadata(tree: ArchiveTree) -> dict[str, Any]:
    """`metadata.json` as a mapping; absent means an empty one (bare file drop)."""
    try:
        raw = tree.read_bytes(METADATA_NAME)
    except FileNotFoundError:
        return {}
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ArchiveError(METADATA_NAME, f"invalid JSON: {error}") from error
    if not isinstance(document, dict):
        raise ArchiveError(METADATA_NAME, "metadata is not a JSON object")
    return cast("dict[str, Any]", document)


def _meta_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ArchiveError(METADATA_NAME, f"'{key}' is not a string")
    if key in _MAX_LENGTHS:
        _check_length(value, METADATA_NAME, key, _MAX_LENGTHS[key])
    return value


def _parse_chapters(tree: ArchiveTree, metadata: dict[str, Any]) -> list[ChapterFile]:
    """Every `chapters/*.md` is the truth; the index only lends its positions.

    The returned order is the reading order: frontmatter position first, the
    index's position next, the order of appearance (sorted file names) last.
    """
    indexed = _chapter_index(metadata)
    parsed: list[tuple[int, int, ChapterFile]] = []
    for order, name in enumerate(tree.chapter_names()):
        chapter = _parse_chapter(tree, name, indexed, order + 1)
        parsed.append((chapter.position, order, chapter))
    parsed.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in parsed]


def _chapter_index(metadata: dict[str, Any]) -> dict[str, int]:
    """`metadata.json`'s chapters index as {file name: position}."""
    value = metadata.get("chapters")
    if value is None:
        return {}
    if not isinstance(value, list):
        raise ArchiveError(METADATA_NAME, "'chapters' is not a list")
    indexed: dict[str, int] = {}
    for entry in cast("list[object]", value):
        if not isinstance(entry, dict):
            raise ArchiveError(METADATA_NAME, "a chapters entry is not an object")
        chapter = cast("dict[str, Any]", entry)
        file = chapter.get("file")
        if not isinstance(file, str):
            raise ArchiveError(METADATA_NAME, "a chapters entry has no 'file'")
        name = file.removeprefix("chapters/")
        indexed[name] = _index_position(chapter.get("position"), name)
    return indexed


def _index_position(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ArchiveError(METADATA_NAME, f"chapters entry '{name}': 'position' is not an integer")
    try:
        return int(value)
    except ValueError as error:
        raise ArchiveError(
            METADATA_NAME, f"chapters entry '{name}': 'position' is not an integer"
        ) from error


def _parse_chapter(
    tree: ArchiveTree, name: str, indexed: dict[str, int], appearance: int
) -> ChapterFile:
    text = _decode(tree.read_bytes(name), name)
    frontmatter, body = _split_frontmatter(text, name)
    title = _fm_str(frontmatter, "title", name)
    # The index is keyed by the bare file name (`_chapter_index` strips the
    # `chapters/` prefix); look the chapter up under the same key.
    index_position = indexed.get(name.removeprefix("chapters/"))
    # Presence, not truthiness: an exported `title: ''` is a value and must
    # come back untitled, not be re-invented from the file stem.
    effective_title = title if title is not None else _deslug(_stem(name))
    _check_length(effective_title, name, "title", _MAX_LENGTHS["title"])
    return ChapterFile(
        title=effective_title,
        position=_fm_int(
            frontmatter,
            "position",
            name,
            appearance if index_position is None else index_position,
        ),
        body=body,
        id=_fm_uuid(frontmatter, "id", name),
        updated=_fm_datetime(frontmatter, "updated", name),
        file=name,
        indexed_position=index_position,
    )


def _parse_entities(tree: ArchiveTree) -> list[EntityFile]:
    """Every `kb/*.md`, in sorted file-name order."""
    entities: list[EntityFile] = []
    for name in tree.kb_names():
        text = _decode(tree.read_bytes(name), name)
        frontmatter, body = _split_frontmatter(text, name)
        entity_name = _fm_str(frontmatter, "name", name)
        entity_type = _fm_str(frontmatter, "type", name)
        # Presence, not truthiness — but a present value must be usable:
        # `name: ''` and `type: ''` are blanks, and blanks refuse, while an
        # absent name falls back to the file stem and an absent type to
        # `generic`. (`title: ''` on chapters stays legal — an untitled
        # chapter is a real state, and nothing else points at it.)
        if entity_name is not None:
            _check_non_blank(entity_name, name, "name")
        if entity_type is not None:
            _check_non_blank(entity_type, name, "type")
        effective_name = entity_name if entity_name is not None else _deslug(_stem(name))
        _check_length(effective_name, name, "name", _MAX_LENGTHS["name"])
        entities.append(
            EntityFile(
                name=effective_name,
                type=entity_type if entity_type is not None else "generic",
                aliases=_fm_str_list(frontmatter, "aliases", name),
                tags=_fm_str_list(frontmatter, "tags", name),
                body=body,
                id=_fm_uuid(frontmatter, "id", name),
                updated=_fm_datetime(frontmatter, "updated", name),
                file=name,
            )
        )
    return entities


def _parse_relations(metadata: dict[str, Any]) -> list[RelationEdge]:
    value = metadata.get("relations")
    if value is None:
        return []
    if not isinstance(value, list):
        raise ArchiveError(METADATA_NAME, "'relations' is not a list")
    edges: list[RelationEdge] = []
    for index, entry in enumerate(cast("list[object]", value), start=1):
        if not isinstance(entry, dict):
            raise ArchiveError(METADATA_NAME, f"relation #{index} is not an object")
        relation = cast("dict[str, Any]", entry)
        label = f"relation #{index}"
        note = relation.get("note")
        if note is not None and not isinstance(note, str):
            raise ArchiveError(METADATA_NAME, f"{label}: 'note' is not a string")
        relation_type = _meta_required(relation, "type", label)
        _check_non_blank(relation_type, METADATA_NAME, "type", label)
        _check_length(relation_type, METADATA_NAME, "type", _MAX_LENGTHS["relation_type"], label)
        edges.append(
            RelationEdge(
                from_name=_meta_required(relation, "from", label),
                relation_type=relation_type,
                to_name=_meta_required(relation, "to", label),
                note=note,
            )
        )
    return edges


def _meta_required(relation: dict[str, Any], key: str, label: str) -> str:
    value = relation.get(key)
    if value is None:
        raise ArchiveError(METADATA_NAME, f"{label} has no '{key}'")
    if not isinstance(value, str):
        raise ArchiveError(METADATA_NAME, f"{label}: '{key}' is not a string")
    return value


def _decode(raw: bytes, relpath: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ArchiveError(relpath, "file is not UTF-8") from error


# ---------------------------------------------------------------------------
# Serialize
# ---------------------------------------------------------------------------


def serialize_archive(archive: NovelArchive) -> dict[str, bytes]:
    """The archive's files, `metadata.json` first, everything deterministic."""
    files: dict[str, bytes] = {}
    chapter_keys = [
        (slugify(chapter.title), chapter.title, chapter.position) for chapter in archive.chapters
    ]
    chapter_slugs = _assign_slugs(chapter_keys)
    chapter_names = [
        f"chapters/{chapter.position:02d}-{slug}.md"
        for chapter, slug in zip(archive.chapters, chapter_slugs, strict=True)
    ]
    entity_keys = [(slugify(entity.name), entity.name) for entity in archive.entities]
    entity_slugs = _assign_slugs(entity_keys)
    entity_names = [f"kb/{slug}.md" for slug in entity_slugs]

    files[METADATA_NAME] = _metadata_bytes(archive, chapter_names)
    for name, chapter in zip(chapter_names, archive.chapters, strict=True):
        files[name] = _chapter_bytes(chapter)
    for name, entity in zip(entity_names, archive.entities, strict=True):
        files[name] = _entity_bytes(entity)
    return files


def _metadata_bytes(archive: NovelArchive, chapter_names: list[str]) -> bytes:
    document: dict[str, Any] = {"title": archive.title}
    document.update(
        {
            key: value
            for key, value in (
                ("author", archive.author),
                ("genre", archive.genre),
                ("blurb", archive.blurb),
                ("language", archive.language),
            )
            if value is not None
        }
    )
    document["chapters"] = [
        {"file": name, "position": chapter.position}
        for name, chapter in zip(chapter_names, archive.chapters, strict=True)
    ]
    relations: list[dict[str, str]] = []
    for edge in archive.relations:
        relation = {"from": edge.from_name, "type": edge.relation_type, "to": edge.to_name}
        if edge.note is not None:
            relation["note"] = edge.note
        relations.append(relation)
    document["relations"] = relations
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _chapter_bytes(chapter: ChapterFile) -> bytes:
    frontmatter: dict[str, Any] = {"title": chapter.title, "position": chapter.position}
    if chapter.id is not None:
        frontmatter["id"] = str(chapter.id)
    if chapter.updated is not None:
        frontmatter["updated"] = chapter.updated.isoformat()
    return _file_bytes(_dump_frontmatter(frontmatter), chapter.body)


def _entity_bytes(entity: EntityFile) -> bytes:
    frontmatter: dict[str, Any] = {
        "type": entity.type,
        "name": entity.name,
        "aliases": entity.aliases,
        "tags": entity.tags,
    }
    if entity.id is not None:
        frontmatter["id"] = str(entity.id)
    if entity.updated is not None:
        frontmatter["updated"] = entity.updated.isoformat()
    return _file_bytes(_dump_frontmatter(frontmatter), entity.body)
