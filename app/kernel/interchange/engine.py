"""The merge engine: one novel out of the database, one archive back in.

The decision loop per item, in the spec's order (D11): **match** — chapters
by frontmatter `id`, entities by `id` else exact casefold `name` — then
**already-current** (the fields the rule revises are equal: no write, no
timestamp bump), then the **revision guard** (the file wins only if its
`updated` is not older than the row's `updated_at`; a missing `updated`
counts as new, not older), then **apply**. Type discrepancies conflict
before the content checks; a type outside the vocabulary refuses the item
entirely; edges are create-only, a differing `note` a conflict; novel
metadata is never applied on merge — every differing key the metadata file
actually carries is reported. Every insert mints a fresh UUID: `id` and
`updated` in frontmatter are match keys only, never stored. The report is
the receipt — counts per class plus one `Conflict` row per refusal, nothing
silent — and the whole import commits once, at the end.

The WP1 invariant travels with the rows: every entity the import births or
revises gets `search_text` (name, aliases, tags). No vector is written — no
read path consumes an entity vector.

The report's `Conflict.file` carries the archive path parse stamps onto
every chapter and entity file (`file` on the dataclasses), falling back to
the chapter title, the entity name, the edge label, or `metadata.json` when
no path is known. A hand-edited disagreement between `metadata.json`'s
index position and a new file's frontmatter position is a reported conflict —
the frontmatter still wins for placement; on matched (revised or
already-current) chapters disagreements are ignored, the stock's position
being the truth merged into.

The name index mirrors each row's *current* name and aliases: a revision
re-registers its row, so the file's own edges follow a rename, and the
pre-rename name stops resolving the moment the rename applies — a later
id-less file still spelling it is a new entity, an edge still spelling it
is a reported absence, never a silent fold. Entity identity matching (rule
1) consults names only; aliases serve edge ends (rule 6), where they are
the WP1 resolution the spec names.

Chapters: new ones append after `max(position) + 1` — 0 on an empty novel,
the house `next_position` convention — in the archive's reading order, which
is the index-then-filename order the parser settled. The stock's position is
the truth being merged into: revisions never move it, and the file's own
position only orders the new appends.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID  # noqa: TC003  runtime: Task 4 serializes ImportReport via get_type_hints

from app.kernel.contracts.models import (
    ENTITY_TYPES,
    Chapter,
    Entity,
    EntityRelation,
    Novel,
)
from app.kernel.contracts.positions import next_chapter_position
from app.kernel.db.base import ScopedRepository
from app.kernel.interchange.format import (
    METADATA_NAME,
    ArchiveError,
    ChapterFile,
    EntityFile,
    NovelArchive,
    RelationEdge,
    parse_archive,
    serialize_archive,
    slugify,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.kernel.interchange.tree import ArchiveTree

_ARCHIVE = "<archive>"
"""The whole archive, when no single file is at fault."""


class NovelNotFoundError(LookupError):
    """The novel does not exist for this user.

    A `LookupError` subclass for the engine's own callers (the previous
    contract), distinct enough that a `KeyError` deep in the merge can never
    masquerade as a missing novel at the HTTP surface.
    """


@dataclass
class Conflict:
    """One item the rules refused, with why.

    `file` names the archive side the reason is about: the path parse stamps
    onto the file (`chapters/…`, `kb/…`), falling back to the chapter title
    or entity name when the file was constructed without one, the edge label
    `from -type-> to` for relations, and `metadata.json` for metadata diffs.
    `code` is the stable machine key the receipt localizes, with `params`
    interpolated; `reason` stays the technical detail — the logs', the tests'
    and the fallback a client uses for a code it does not know.
    """

    file: str
    reason: str
    code: str
    params: dict[str, str] = field(default_factory=dict[str, str])


@dataclass
class ImportReport:
    """What one import did, per class — the receipt, nothing silent.

    Tally semantics: a renamed entity counts once as `entities_renamed`,
    whether or not its body also changed; `entities_revised` counts content
    revisions (body, aliases, tags) without a rename. Every matched item
    increments exactly one of new / revised / renamed / already_current;
    an item refused by a conflict increments nothing.
    """

    novel_id: UUID
    chapters_new: int = 0
    chapters_revised: int = 0
    chapters_already_current: int = 0
    entities_new: int = 0
    entities_revised: int = 0
    entities_renamed: int = 0
    entities_already_current: int = 0
    relations_created: int = 0
    relations_already_current: int = 0
    conflicts: list[Conflict] = field(default_factory=list[Conflict])
    metadata_conflicts: list[str] = field(default_factory=list[str])


# ---------------------------------------------------------------------------
# The WP1 invariant, re-implemented against the kernel: the two derived
# columns every entity write path maintains. Shared invariant, not shared
# code — the engine never imports a capability.
# ---------------------------------------------------------------------------


def _search_text(name: str, aliases: Sequence[str], tags: Sequence[str]) -> str:
    """The maintained concatenation the trigram search runs over."""
    return " ".join([name, *aliases, *tags])


class _Entities(ScopedRepository[Entity]):
    model = Entity

    async def list_for_novel(self, novel_id: UUID) -> Sequence[Entity]:
        """The novel's entities, oldest first, tie-broken by id."""
        result = await self.session.scalars(
            self.query().where(Entity.novel_id == novel_id).order_by(Entity.created_at, Entity.id)
        )
        return result.all()

    async def create(
        self,
        novel_id: UUID,
        name: str,
        type: str,
        content: str,
        aliases: Sequence[str],
        tags: Sequence[str],
    ) -> Entity:
        """Flush a new entity; `search_text` is computed here, the one writer."""
        entity = Entity(
            user_id=self.user_id,
            novel_id=novel_id,
            name=name,
            type=type,
            content=content,
            aliases=list(aliases),
            tags=list(tags),
            search_text=_search_text(name, aliases, tags),
        )
        self.session.add(entity)
        await self.session.flush()
        return entity


# ---------------------------------------------------------------------------
# Scoped access over the shared models — kernel reading kernel contracts, the
# sanctioned seam (the capability repositories are out of reach by design).
# ---------------------------------------------------------------------------


class _Novels(ScopedRepository[Novel]):
    model = Novel

    async def get(self, novel_id: UUID) -> Novel | None:
        return await self.session.scalar(self.query().where(Novel.id == novel_id))

    async def create(
        self,
        title: str,
        *,
        author: str | None,
        genre: str | None,
        blurb: str | None,
        language: str | None,
    ) -> Novel:
        novel = Novel(
            user_id=self.user_id,
            title=title,
            author=author,
            genre=genre,
            blurb=blurb,
            language=language,
        )
        self.session.add(novel)
        await self.session.flush()
        return novel


class _Chapters(ScopedRepository[Chapter]):
    model = Chapter

    async def list_for_novel(self, novel_id: UUID) -> Sequence[Chapter]:
        """Reading order: position, then creation, then id — deterministic."""
        result = await self.session.scalars(
            self.query()
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.position, Chapter.created_at, Chapter.id)
        )
        return result.all()

    async def create(self, novel_id: UUID, title: str, position: int, body: str) -> Chapter:
        chapter = Chapter(
            user_id=self.user_id, novel_id=novel_id, title=title, position=position, body=body
        )
        self.session.add(chapter)
        await self.session.flush()
        return chapter


class _Edges(ScopedRepository[EntityRelation]):
    model = EntityRelation

    async def list_for_novel(self, entity_ids: Sequence[UUID]) -> Sequence[EntityRelation]:
        """Every edge whose source is one of the novel's entities, scoped,
        oldest first with the id as tie-break — the order that keeps an
        export's `relations` array byte-stable across exports."""
        if not entity_ids:
            return []
        result = await self.session.scalars(
            self.query()
            .where(EntityRelation.from_entity_id.in_(entity_ids))
            .order_by(EntityRelation.created_at, EntityRelation.id)
        )
        return result.all()

    async def create(
        self, from_entity_id: UUID, to_entity_id: UUID, relation_type: str, note: str | None
    ) -> EntityRelation:
        relation = EntityRelation(
            user_id=self.user_id,
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relation_type=relation_type,
            note=note,
        )
        self.session.add(relation)
        await self.session.flush()
        return relation


class _NameIndex:
    """A novel's entities by name and by alias, trimmed and casefolded.

    Two resolutions, kept apart on purpose: :meth:`resolve_name` is the
    entity identity match (rule 1 — `id`, else exact casefold *name*), where
    an alias is never consulted, because an alias points at a canon row
    without being one; :meth:`resolve` adds the aliases and serves the edge
    ends (rule 6), where the WP1 suggestion-accept resolution the spec names
    reads both. Entities the import births join the pool, and a revision
    re-registers its row: the index always mirrors the row's current name
    and aliases, so the file's own edges follow a rename while the
    pre-rename name stops resolving the moment the rename applies — a later
    id-less file still spelling it is a new entity, an edge still spelling
    it a reported absence, never a silent fold.
    """

    def __init__(self, entities: Sequence[Entity]) -> None:
        self._by_name: dict[str, list[Entity]] = {}
        self._by_alias: dict[str, list[Entity]] = {}
        self._keys: dict[UUID, tuple[str, tuple[str, ...]]] = {}
        for entity in entities:
            self.add(entity)

    def add(self, entity: Entity) -> None:
        name_key = entity.name.strip().casefold()
        alias_keys = tuple(alias.strip().casefold() for alias in entity.aliases)
        self._by_name.setdefault(name_key, []).append(entity)
        for key in alias_keys:
            self._by_alias.setdefault(key, []).append(entity)
        self._keys[entity.id] = (name_key, alias_keys)

    def replace(self, entity: Entity) -> None:
        """Re-register a revised row: the stale keys are released before the
        current name and aliases bind, so no old spelling keeps pointing at
        the row it no longer names. (Releasing an unregistered id filters by
        row id and is a no-op.)"""
        old_name_key, old_alias_keys = self._keys.get(entity.id, ("", ()))
        rows = [row for row in self._by_name.get(old_name_key, []) if row.id != entity.id]
        if rows:
            self._by_name[old_name_key] = rows
        else:
            self._by_name.pop(old_name_key, None)
        for key in old_alias_keys:
            rows = [row for row in self._by_alias.get(key, []) if row.id != entity.id]
            if rows:
                self._by_alias[key] = rows
            else:
                self._by_alias.pop(key, None)
        self.add(entity)

    def resolve_name(self, wanted: str) -> list[Entity]:
        """Exact trimmed-casefold NAME matches — entity identity only."""
        return list(self._by_name.get(wanted.strip().casefold(), []))

    def resolve(self, wanted: str) -> list[Entity]:
        """Exact trimmed-casefold matches over names and aliases — the edge
        ends' resolution; empty means absent, several means ambiguous."""
        key = wanted.strip().casefold()
        found = {entity.id: entity for entity in self._by_name.get(key, [])}
        for entity in self._by_alias.get(key, []):
            found.setdefault(entity.id, entity)
        return list(found.values())


def _aware(moment: datetime | None) -> datetime | None:
    """A hand-written `updated` without an offset means UTC: rule 3 compares
    timezone-aware instants, and exports always carry one."""
    if moment is None or moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=UTC)


def _metadata(tree: ArchiveTree) -> dict[str, Any]:
    """The raw metadata mapping — parse already validated its values, but
    key *presence* is lost in the dataclasses (an absent key and an explicit
    null parse the same), and presence is what a merge compares."""
    try:
        raw = tree.read_bytes(METADATA_NAME)
    except FileNotFoundError:
        return {}
    document = json.loads(raw)
    return cast("dict[str, Any]", document)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


async def export_novel(
    session: AsyncSession, user_id: UUID, novel_id: UUID
) -> tuple[str, dict[str, bytes]]:
    """One novel as the interchange format: the title's slug and the files.

    Scoped to the user; a novel that does not exist or belongs to someone
    else raises `NovelNotFoundError` — the scoped absence is one answer.
    """
    novel = await _Novels(session, user_id).get(novel_id)
    if novel is None:
        raise NovelNotFoundError(f"novel {novel_id} does not exist for this user")
    chapters = await _Chapters(session, user_id).list_for_novel(novel_id)
    entities = await _Entities(session, user_id).list_for_novel(novel_id)
    by_id = {entity.id: entity for entity in entities}
    edges = await _Edges(session, user_id).list_for_novel([entity.id for entity in entities])
    archive = NovelArchive(
        title=novel.title,
        author=novel.author,
        genre=novel.genre,
        blurb=novel.blurb,
        language=novel.language,
        chapters=[
            ChapterFile(
                title=chapter.title,
                position=chapter.position,
                body=chapter.body,
                id=chapter.id,
                updated=chapter.updated_at,
            )
            for chapter in chapters
        ],
        entities=[
            EntityFile(
                name=entity.name,
                type=entity.type,
                aliases=list(entity.aliases),
                tags=list(entity.tags),
                body=entity.content,
                id=entity.id,
                updated=entity.updated_at,
            )
            for entity in entities
        ],
        relations=[
            RelationEdge(
                from_name=by_id[relation.from_entity_id].name,
                relation_type=relation.relation_type,
                to_name=by_id[relation.to_entity_id].name,
                note=relation.note,
            )
            for relation in edges
        ],
    )
    return slugify(novel.title), serialize_archive(archive)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


async def import_archive(
    session: AsyncSession, user_id: UUID, tree: ArchiveTree, novel_id: UUID | None
) -> ImportReport:
    """Import one archive: as a new novel when `novel_id` is None (title
    required, author/genre/blurb/language applied), otherwise merged into the
    existing novel by the spec's eight rules. Commits once, at the end.

    An archive carrying no chapters, no entities and no relations refuses
    outright — a `zip -r` envelope of empty directories must not merge as a
    silent 0/0 success. A novel that does not exist or belongs to someone
    else raises `NovelNotFoundError`.
    """
    archive = parse_archive(tree)
    if not archive.chapters and not archive.entities and not archive.relations:
        raise ArchiveError(
            _ARCHIVE, "the archive carries no chapters, no entities and no relations"
        )

    if novel_id is None:
        if not archive.title.strip():
            raise ArchiveError(METADATA_NAME, "a new novel needs a title")
        novel = await _Novels(session, user_id).create(
            archive.title,
            author=archive.author,
            genre=archive.genre,
            blurb=archive.blurb,
            language=archive.language,
        )
        report = ImportReport(novel_id=novel.id)
    else:
        novel = await _Novels(session, user_id).get(novel_id)
        if novel is None:
            raise NovelNotFoundError(f"novel {novel_id} does not exist for this user")
        report = ImportReport(novel_id=novel.id)
        _report_metadata_conflicts(novel, _metadata(tree), report)

    await _merge_chapters(session, user_id, novel, archive, report)
    names = await _merge_entities(session, user_id, novel, archive, report)
    await _merge_relations(session, user_id, novel, archive, report, names)
    # The shelf's hero is the last-touched novel, and the chapter write path
    # bumps `novel.updated_at` on every edit. A merge that wrote anything is a
    # touch like any other; one that only confirmed the stock is not.
    wrote = (
        report.chapters_new
        + report.chapters_revised
        + report.entities_new
        + report.entities_revised
        + report.entities_renamed
        + report.relations_created
    )
    if novel_id is not None and wrote:
        novel.updated_at = datetime.now(UTC)
    await session.commit()
    return report


async def _merge_chapters(
    session: AsyncSession, user_id: UUID, novel: Novel, archive: NovelArchive, report: ImportReport
) -> None:
    """Rule 4: revision applies title and body; new chapters append.

    Chapters match by frontmatter `id` alone — a hand-written file without
    one is new. The stock's position is the truth: revisions never move it,
    and new chapters take append slots, not their file's position. A new
    file whose frontmatter position disagrees with `metadata.json`'s index
    position still imports (the frontmatter wins for placement) and the
    disagreement is a reported conflict; on matched chapters it is ignored.
    """
    chapters = _Chapters(session, user_id)
    # The one allocator, and with it the novel-row lock: an import landing
    # beside a creation — or beside another import — must not take the same
    # number, and the lock is what makes the read see the other writer's
    # committed chapters (#521).
    position = await next_chapter_position(session, user_id=user_id, novel_id=novel.id)
    stock = await chapters.list_for_novel(novel.id)
    by_id = {chapter.id: chapter for chapter in stock}
    for file_chapter in archive.chapters:
        row = by_id.get(file_chapter.id) if file_chapter.id is not None else None
        if row is None:
            if (
                file_chapter.indexed_position is not None
                and file_chapter.indexed_position != file_chapter.position
            ):
                report.conflicts.append(
                    Conflict(
                        file_chapter.file or file_chapter.title,
                        "position disagreement: the metadata index says "
                        f"{file_chapter.indexed_position}, the frontmatter says "
                        f"{file_chapter.position} — the frontmatter wins for placement",
                        code="position_disagree",
                        params={
                            "index_position": str(file_chapter.indexed_position),
                            "file_position": str(file_chapter.position),
                        },
                    )
                )
            await chapters.create(novel.id, file_chapter.title, position, file_chapter.body)
            position += 1
            report.chapters_new += 1
            continue
        if row.title == file_chapter.title and row.body == file_chapter.body:
            report.chapters_already_current += 1
            continue
        file_updated = _aware(file_chapter.updated)
        if file_updated is None or file_updated >= row.updated_at:
            row.title = file_chapter.title
            row.body = file_chapter.body
            report.chapters_revised += 1
        else:
            report.conflicts.append(
                Conflict(
                    file_chapter.file or file_chapter.title,
                    "stale revision: the file's updated "
                    f"({file_updated.isoformat()}) is older than the chapter's "
                    f"updated_at ({row.updated_at.isoformat()}) — not applied",
                    code="stale_revision",
                    params={
                        "file_updated": file_updated.isoformat(),
                        "stock_updated": row.updated_at.isoformat(),
                    },
                )
            )


async def _merge_entities(
    session: AsyncSession,
    user_id: UUID,
    novel: Novel,
    archive: NovelArchive,
    report: ImportReport,
) -> _NameIndex:
    """Rules 1, 3, 5: match, guard, apply body/aliases/tags/name.

    A type outside the vocabulary refuses the item outright; a type
    discrepancy between a matched file and its stock row is a conflict that
    leaves the row untouched — checked before the content checks, so even an
    otherwise-identical file cannot sneak a type change through. Identity is
    the id, else the exact casefold NAME — never an alias, which would fold
    a new row into the canon entry it merely points at. A rename tallies
    once as renamed and never also as revised, and the name index is
    re-registered after every applied revision so the file's own edges
    follow the new name while the old one stops resolving. Every birth and
    every revision recomputes `search_text` and the vector in this
    transaction.
    """
    entities = _Entities(session, user_id)
    stock = await entities.list_for_novel(novel.id)
    by_id = {entity.id: entity for entity in stock}
    names = _NameIndex(stock)
    for file_entity in archive.entities:
        conflict_file = file_entity.file or file_entity.name
        if file_entity.type not in ENTITY_TYPES:
            report.conflicts.append(
                Conflict(
                    conflict_file,
                    f"unknown entity type '{file_entity.type}' — not one of "
                    f"{'|'.join(ENTITY_TYPES)}; nothing created",
                    code="unknown_type",
                    params={"type": file_entity.type},
                )
            )
            continue
        row = by_id.get(file_entity.id) if file_entity.id is not None else None
        if row is None:
            matches = names.resolve_name(file_entity.name)
            if len(matches) > 1:
                report.conflicts.append(
                    Conflict(
                        conflict_file,
                        "the name matches several entities of this novel — not applied",
                        code="ambiguous_name",
                        params={"name": file_entity.name},
                    )
                )
                continue
            row = matches[0] if matches else None
        if row is None:
            created = await entities.create(
                novel.id,
                file_entity.name,
                file_entity.type,
                file_entity.body,
                file_entity.aliases,
                file_entity.tags,
            )
            names.add(created)
            report.entities_new += 1
            continue
        if row.type != file_entity.type:
            report.conflicts.append(
                Conflict(
                    conflict_file,
                    f"type discrepancy: the file says '{file_entity.type}', "
                    f"the stock row is '{row.type}' — not applied",
                    code="type_discrepancy",
                    params={"file_type": file_entity.type, "stock_type": row.type},
                )
            )
            continue
        renamed = row.name != file_entity.name
        changed = (
            renamed
            or row.content != file_entity.body
            or list(row.aliases) != file_entity.aliases
            or list(row.tags) != file_entity.tags
        )
        if not changed:
            report.entities_already_current += 1
            continue
        file_updated = _aware(file_entity.updated)
        if file_updated is not None and file_updated < row.updated_at:
            report.conflicts.append(
                Conflict(
                    conflict_file,
                    "stale revision: the file's updated "
                    f"({file_updated.isoformat()}) is older than the entity's "
                    f"updated_at ({row.updated_at.isoformat()}) — not applied",
                    code="stale_revision",
                    params={
                        "file_updated": file_updated.isoformat(),
                        "stock_updated": row.updated_at.isoformat(),
                    },
                )
            )
            continue
        row.name = file_entity.name
        row.content = file_entity.body
        row.aliases = list(file_entity.aliases)
        row.tags = list(file_entity.tags)
        row.search_text = _search_text(row.name, row.aliases, row.tags)
        names.replace(row)
        if renamed:
            report.entities_renamed += 1
        else:
            report.entities_revised += 1
    return names


async def _merge_relations(
    session: AsyncSession,
    user_id: UUID,
    novel: Novel,
    archive: NovelArchive,
    report: ImportReport,
    names: _NameIndex,
) -> None:
    """Rule 6: edges are create-only. Both ends resolve by name (and alias)
    within the novel, created rows included; an identical edge is already
    current, the same edge with a differing note a conflict, and neither is
    ever rewritten."""
    edges = _Edges(session, user_id)
    novel_entities = await _Entities(session, user_id).list_for_novel(novel.id)
    stock = await edges.list_for_novel([entity.id for entity in novel_entities])
    occupied = {
        (relation.from_entity_id, relation.to_entity_id, relation.relation_type): relation
        for relation in stock
    }
    for edge in archive.relations:
        label = f"{edge.from_name} -{edge.relation_type}-> {edge.to_name}"
        sources = names.resolve(edge.from_name)
        if not sources:
            report.conflicts.append(
                Conflict(
                    label,
                    f"'{edge.from_name}' does not name an entity of this novel — edge not created",
                    code="edge_target_missing",
                    params={"name": edge.from_name},
                )
            )
            continue
        if len(sources) > 1:
            report.conflicts.append(
                Conflict(
                    label,
                    f"'{edge.from_name}' matches several entities of this novel — edge not created",
                    code="ambiguous_edge_end",
                    params={"edge": label, "name": edge.from_name},
                )
            )
            continue
        targets = names.resolve(edge.to_name)
        if not targets:
            report.conflicts.append(
                Conflict(
                    label,
                    f"'{edge.to_name}' does not name an entity of this novel — edge not created",
                    code="edge_target_missing",
                    params={"name": edge.to_name},
                )
            )
            continue
        if len(targets) > 1:
            report.conflicts.append(
                Conflict(
                    label,
                    f"'{edge.to_name}' matches several entities of this novel — edge not created",
                    code="ambiguous_edge_end",
                    params={"edge": label, "name": edge.to_name},
                )
            )
            continue
        source, target = sources[0], targets[0]
        existing = occupied.get((source.id, target.id, edge.relation_type))
        if existing is not None:
            if existing.note == edge.note:
                report.relations_already_current += 1
            else:
                report.conflicts.append(
                    Conflict(
                        label,
                        f"the edge exists with note {existing.note!r}, "
                        f"the file says {edge.note!r} — not applied",
                        code="edge_note_differs",
                        params={"edge": label},
                    )
                )
            continue
        created = await edges.create(source.id, target.id, edge.relation_type, edge.note)
        occupied[(created.from_entity_id, created.to_entity_id, created.relation_type)] = created
        report.relations_created += 1


def _report_metadata_conflicts(
    novel: Novel, metadata: dict[str, Any], report: ImportReport
) -> None:
    """Rule 7: merging never applies novel metadata — every key the metadata
    file actually carries and differs is reported. An absent key is not an
    opinion: a bare file drop merges without five spurious conflicts."""
    stock: dict[str, str | None] = {
        "title": novel.title,
        "author": novel.author,
        "genre": novel.genre,
        "blurb": novel.blurb,
        "language": novel.language,
    }
    for key, value in stock.items():
        if key not in metadata:
            continue
        if metadata[key] != value:
            report.metadata_conflicts.append(key)
            report.conflicts.append(
                Conflict(
                    METADATA_NAME,
                    f"{key} differs — not applied",
                    code="metadata_differs",
                    params={"field": key},
                )
            )
