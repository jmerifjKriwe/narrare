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

The WP1 invariants travel with the rows: every entity the import births or
revises gets `search_text` (name, aliases, tags) and the synchronous
embedding (identity words plus the body, capped at 20 000 characters for
the vector only), width-guarded against the stored corpus like accept does.
The provider is the kernel's env-selected one — the engine takes no
dependency argument, these signatures are the HTTP surface's contract.

Two format facts are recorded here rather than papered over: `parse_archive`
returns chapter titles and entity names, not archive file names, so
`Conflict.file` carries that identifier instead of a path; and the
frontmatter-vs-index position precedence is settled inside the parser
(frontmatter wins, then the index, then file order), so a hand-edited
disagreement between the two cannot be detected or reported here. Carrying
the file name in the parsed dataclasses is the one-line format change that
would close both; it belongs to the format's own task, not to a
re-implementation of its parser in the engine.

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

from sqlalchemy import select

from app.kernel.contracts.models import (
    ENTITY_TYPES,
    Chapter,
    Entity,
    EntityRelation,
    Novel,
)
from app.kernel.db.base import ScopedRepository
from app.kernel.embeddings import get_embedding_provider
from app.kernel.interchange.format import (
    METADATA_NAME,
    ArchiveError,
    ChapterFile,
    EntityFile,
    NovelArchive,
    RelationEdge,
    _slugify,  # pyright: ignore[reportPrivateUsage]  the export slug IS the format's slug rule
    parse_archive,
    serialize_archive,
)
from app.kernel.retrieval import EmbeddingMismatchError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.kernel.embeddings import EmbeddingProvider
    from app.kernel.interchange.tree import ArchiveTree

EMBEDDING_CONTENT_LIMIT = 20_000
"""The most body an embedding text carries, in characters (D5) — the knowledge
capability's exact cap. Storage keeps the full body."""

_ARCHIVE = "<archive>"
"""The whole archive, when no single file is at fault."""


@dataclass
class Conflict:
    """One item the rules refused, with why.

    `file` names the archive side the reason is about. Parse hands the engine
    titles and names, not paths (the format's dataclasses carry no file
    name), so it holds the chapter title, the entity name, an edge label of
    the shape `from -type-> to`, or `metadata.json` — the receipt renders
    `file — reason` either way.
    """

    file: str
    reason: str


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


def _embedding_text(entity: Entity) -> str:
    """The text a vector is built from: identity words, then the capped body."""
    return " ".join(
        [
            entity.name,
            *entity.aliases,
            *entity.tags,
            entity.content[:EMBEDDING_CONTENT_LIMIT],
        ]
    )


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

    async def stored_entity_width(self) -> int | None:
        """The width this user's entity corpus was embedded at; None when none is."""
        result = await self.session.scalars(
            select(Entity.embedding)
            .where(Entity.user_id == self.user_id, Entity.embedding.is_not(None))
            .order_by(Entity.created_at)
            .limit(1)
        )
        widths = [len(vector) for vector in result.all() if vector is not None]
        return widths[0] if widths else None


async def _embed_entity(
    session: AsyncSession, user_id: UUID, entity: Entity, provider: EmbeddingProvider
) -> None:
    """Embed in the import's transaction, width-guarded like accept does.

    The corpus keeps one width: the first set vector's width is the user's,
    and a model answering at another width raises instead of silently
    degrading search. The assignment stays in-memory until the caller's
    single commit.
    """
    [vector] = await provider.embed([_embedding_text(entity)])
    stored = await _Entities(session, user_id).stored_entity_width()
    if stored is not None and stored != len(vector):
        raise EmbeddingMismatchError(stored, len(vector))
    entity.embedding = vector


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
        """Every edge whose source is one of the novel's entities, scoped."""
        if not entity_ids:
            return []
        result = await self.session.scalars(
            self.query().where(EntityRelation.from_entity_id.in_(entity_ids))
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
    """A novel's entities by name and alias, trimmed and casefolded — the
    resolution WP1's suggestion-accept uses. Entities the import births join
    the pool, so a new novel's edges resolve against its own just-created
    rows."""

    def __init__(self, entities: Sequence[Entity]) -> None:
        self._by_name: dict[str, list[Entity]] = {}
        self._by_alias: dict[str, list[Entity]] = {}
        for entity in entities:
            self.add(entity)

    def add(self, entity: Entity) -> None:
        self._by_name.setdefault(entity.name.strip().casefold(), []).append(entity)
        for alias in entity.aliases:
            self._by_alias.setdefault(alias.strip().casefold(), []).append(entity)

    def resolve(self, wanted: str) -> list[Entity]:
        """Exact trimmed-casefold matches over names and aliases, deduped;
        empty means absent, several means ambiguous — both are reported."""
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
    else raises `LookupError` — the scoped absence is one answer.
    """
    novel = await _Novels(session, user_id).get(novel_id)
    if novel is None:
        raise LookupError(f"novel {novel_id} does not exist for this user")
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
    return _slugify(novel.title), serialize_archive(archive)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


async def import_archive(
    session: AsyncSession, user_id: UUID, tree: ArchiveTree, novel_id: UUID | None
) -> ImportReport:
    """Import one archive: as a new novel when `novel_id` is None (title
    required, author/genre/blurb/language applied), otherwise merged into the
    existing novel by the spec's eight rules. Commits once, at the end.

    An archive carrying no chapters and no entities refuses outright — a
    `zip -r` envelope of empty directories must not merge as a silent 0/0
    success. A novel that does not exist or belongs to someone else raises
    `LookupError`.
    """
    archive = parse_archive(tree)
    if not archive.chapters and not archive.entities:
        raise ArchiveError(_ARCHIVE, "the archive carries no chapters and no entities")

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
            raise LookupError(f"novel {novel_id} does not exist for this user")
        report = ImportReport(novel_id=novel.id)
        _report_metadata_conflicts(novel, _metadata(tree), report)

    provider = get_embedding_provider()
    await _merge_chapters(session, user_id, novel, archive, report)
    names = await _merge_entities(session, user_id, novel, archive, report, provider)
    await _merge_relations(session, user_id, novel, archive, report, names)
    await session.commit()
    return report


async def _merge_chapters(
    session: AsyncSession, user_id: UUID, novel: Novel, archive: NovelArchive, report: ImportReport
) -> None:
    """Rule 4: revision applies title and body; new chapters append.

    Chapters match by frontmatter `id` alone — a hand-written file without
    one is new. The stock's position is the truth: revisions never move it,
    and new chapters take append slots, not their file's position.
    """
    chapters = _Chapters(session, user_id)
    stock = await chapters.list_for_novel(novel.id)
    by_id = {chapter.id: chapter for chapter in stock}
    position = max((chapter.position for chapter in stock), default=-1) + 1
    for file_chapter in archive.chapters:
        row = by_id.get(file_chapter.id) if file_chapter.id is not None else None
        if row is None:
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
                    file_chapter.title,
                    "stale revision: the file's updated "
                    f"({file_updated.isoformat()}) is older than the chapter's "
                    f"updated_at ({row.updated_at.isoformat()}) — not applied",
                )
            )


async def _merge_entities(
    session: AsyncSession,
    user_id: UUID,
    novel: Novel,
    archive: NovelArchive,
    report: ImportReport,
    provider: EmbeddingProvider,
) -> _NameIndex:
    """Rules 1, 3, 5: match, guard, apply body/aliases/tags/name.

    A type outside the vocabulary refuses the item outright; a type
    discrepancy between a matched file and its stock row is a conflict that
    leaves the row untouched — checked before the content checks, so even an
    otherwise-identical file cannot sneak a type change through. A rename
    tallies once as renamed and never also as revised. Every birth and every
    revision recomputes `search_text` and the vector in this transaction.
    """
    entities = _Entities(session, user_id)
    stock = await entities.list_for_novel(novel.id)
    by_id = {entity.id: entity for entity in stock}
    names = _NameIndex(stock)
    for file_entity in archive.entities:
        if file_entity.type not in ENTITY_TYPES:
            report.conflicts.append(
                Conflict(
                    file_entity.name,
                    f"unknown entity type '{file_entity.type}' — not one of "
                    f"{'|'.join(ENTITY_TYPES)}; nothing created",
                )
            )
            continue
        row = by_id.get(file_entity.id) if file_entity.id is not None else None
        if row is None:
            matches = names.resolve(file_entity.name)
            if len(matches) > 1:
                report.conflicts.append(
                    Conflict(
                        file_entity.name,
                        "the name matches several entities of this novel — not applied",
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
            await _embed_entity(session, user_id, created, provider)
            report.entities_new += 1
            continue
        if row.type != file_entity.type:
            report.conflicts.append(
                Conflict(
                    file_entity.name,
                    f"type discrepancy: the file says '{file_entity.type}', "
                    f"the stock row is '{row.type}' — not applied",
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
                    file_entity.name,
                    "stale revision: the file's updated "
                    f"({file_updated.isoformat()}) is older than the entity's "
                    f"updated_at ({row.updated_at.isoformat()}) — not applied",
                )
            )
            continue
        row.name = file_entity.name
        row.content = file_entity.body
        row.aliases = list(file_entity.aliases)
        row.tags = list(file_entity.tags)
        row.search_text = _search_text(row.name, row.aliases, row.tags)
        await _embed_entity(session, user_id, row, provider)
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
                )
            )
            continue
        if len(sources) > 1:
            report.conflicts.append(
                Conflict(
                    label,
                    f"'{edge.from_name}' matches several entities of this novel — edge not created",
                )
            )
            continue
        targets = names.resolve(edge.to_name)
        if not targets:
            report.conflicts.append(
                Conflict(
                    label,
                    f"'{edge.to_name}' does not name an entity of this novel — edge not created",
                )
            )
            continue
        if len(targets) > 1:
            report.conflicts.append(
                Conflict(
                    label,
                    f"'{edge.to_name}' matches several entities of this novel — edge not created",
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
            report.conflicts.append(Conflict(METADATA_NAME, f"{key} differs — not applied"))
