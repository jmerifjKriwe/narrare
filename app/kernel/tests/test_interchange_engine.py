"""The merge engine against the real database: export, merge, refuse, report.

These tests pin the spec's decision loop (match → already-current → revision
guard → apply) over the shared models: the round trip out of and back into the
database mints fresh UUIDs but identical content, re-importing an archive is
idempotent without touching a timestamp, a stale file never overwrites newer
prose, renames ride the foreign keys, unknown types and note-differing edges
are reported conflicts, novel metadata is not applied on merge, and the
WP1 invariants — `search_text` and the synchronous embedding — hold for every
entity the import births or revises.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.kernel.contracts.models import Chapter, Entity, EntityRelation, Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.embeddings import FakeEmbeddingProvider
from app.kernel.interchange import (
    ArchiveError,
    ArchiveTree,
    ChapterFile,
    EntityFile,
    NovelArchive,
    RelationEdge,
    parse_archive,
    serialize_archive,
)
from app.kernel.interchange.engine import ImportReport, export_novel, import_archive

pytestmark = pytest.mark.usefixtures("schema", "empty_tables")

OWNER = uuid4()
STALE_BASE = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
async def a_user(empty_tables: None) -> None:
    """The users row every user-owned row of this suite reaches."""
    await seed_user(OWNER)


async def _seed_novel() -> UUID:
    """The stock novel: two chapters, two entities, one edge between them."""
    async with Session() as session:
        novel = Novel(
            user_id=OWNER,
            title="Der Wanderer",
            author="E. A. Guest",
            genre="Fantasy",
            blurb="Ein Roman über Wege.",
            language="de",
        )
        session.add(novel)
        await session.flush()
        mira = Entity(
            user_id=OWNER,
            novel_id=novel.id,
            name="Mira",
            type="character",
            content="Jung.\n",
            aliases=["Die Wanderin"],
            tags=["protagonist"],
        )
        emile = Entity(
            user_id=OWNER,
            novel_id=novel.id,
            name="Émile Zola",
            type="character",
            content="Schriftsteller.\n",
            aliases=[],
            tags=[],
        )
        session.add_all([mira, emile])
        await session.flush()
        session.add(
            EntityRelation(
                user_id=OWNER,
                from_entity_id=mira.id,
                to_entity_id=emile.id,
                relation_type="knows",
                note="aus Briefen",
            )
        )
        session.add_all(
            [
                Chapter(
                    user_id=OWNER,
                    novel_id=novel.id,
                    title="Ankunft",
                    position=0,
                    body="Der Regen hörte auf.\n",
                ),
                Chapter(
                    user_id=OWNER,
                    novel_id=novel.id,
                    title="Der Pfad",
                    position=1,
                    body="Zweiter Teil.\n",
                ),
            ]
        )
        await session.commit()
        return novel.id


async def _export(novel_id: UUID) -> tuple[str, dict[str, bytes]]:
    """Export through the engine, the way Task 4's ZIP route will."""
    async with Session() as session:
        return await export_novel(session, OWNER, novel_id)


async def _import(tree: ArchiveTree, novel_id: UUID | None) -> ImportReport:
    """Import through the engine, one transaction, committed."""
    async with Session() as session:
        return await import_archive(session, OWNER, tree, novel_id)


async def _rows(novel_id: UUID) -> tuple[list[Chapter], list[Entity], list[EntityRelation]]:
    """The novel's chapters, entities and edges, read fresh from the database."""
    async with Session() as session:
        chapters = (
            await session.scalars(
                select(Chapter)
                .where(Chapter.novel_id == novel_id, Chapter.user_id == OWNER)
                .order_by(Chapter.position)
            )
        ).all()
        entities = (
            await session.scalars(
                select(Entity)
                .where(Entity.novel_id == novel_id, Entity.user_id == OWNER)
                .order_by(Entity.created_at)
            )
        ).all()
        edges = (
            await session.scalars(
                select(EntityRelation).where(
                    EntityRelation.user_id == OWNER,
                    EntityRelation.from_entity_id.in_([entity.id for entity in entities]),
                )
            )
        ).all()
        return list(chapters), list(entities), list(edges)


async def _novel_row(novel_id: UUID) -> Novel:
    async with Session() as session:
        novel = await session.get(Novel, novel_id)
    assert novel is not None
    return novel


async def _chapters(novel_id: UUID) -> list[Chapter]:
    chapters, _, _ = await _rows(novel_id)
    return chapters


async def _entities(novel_id: UUID) -> list[Entity]:
    _, entities, _ = await _rows(novel_id)
    return entities


async def _novel_count() -> int:
    """How many novels this user owns — the refused path must not add one."""
    async with Session() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(Novel).where(Novel.user_id == OWNER)
            )
            or 0
        )


async def test_export_then_import_as_new_is_identical(a_user: None) -> None:
    """Export → import as a new novel: same content, all-new UUIDs."""
    novel_id = await _seed_novel()
    slug, files = await _export(novel_id)
    assert slug == "der-wanderer"

    report = await _import(ArchiveTree(files), None)
    assert report.novel_id != novel_id
    assert report.conflicts == []
    assert report.metadata_conflicts == []

    old_chapters, old_entities, old_edges = await _rows(novel_id)
    new_chapters, new_entities, new_edges = await _rows(report.novel_id)
    assert [c.title for c in new_chapters] == [c.title for c in old_chapters]
    assert [c.body for c in new_chapters] == [c.body for c in old_chapters]
    assert [c.position for c in new_chapters] == [0, 1]
    assert {c.id for c in new_chapters}.isdisjoint({c.id for c in old_chapters})

    old_by_name = {e.name: e for e in old_entities}
    new_by_name = {e.name: e for e in new_entities}
    assert set(new_by_name) == set(old_by_name)
    for name, new_entity in new_by_name.items():
        old_entity = old_by_name[name]
        assert (new_entity.type, new_entity.content, new_entity.aliases, new_entity.tags) == (
            old_entity.type,
            old_entity.content,
            old_entity.aliases,
            old_entity.tags,
        )
    assert {e.id for e in new_entities}.isdisjoint({e.id for e in old_entities})

    assert len(new_edges) == len(old_edges) == 1
    edge = new_edges[0]
    new_name_by_id = {e.id: e.name for e in new_entities}
    assert (
        new_name_by_id[edge.from_entity_id],
        new_name_by_id[edge.to_entity_id],
        edge.relation_type,
        edge.note,
    ) == ("Mira", "Émile Zola", "knows", "aus Briefen")

    new_novel = await _novel_row(report.novel_id)
    assert (
        new_novel.title,
        new_novel.author,
        new_novel.genre,
        new_novel.blurb,
        new_novel.language,
    ) == ("Der Wanderer", "E. A. Guest", "Fantasy", "Ein Roman über Wege.", "de")


async def test_reimport_same_archive_is_already_current(a_user: None) -> None:
    """The same archive twice: everything already current, no timestamp moves."""
    novel_id = await _seed_novel()
    _, files = await _export(novel_id)
    before = {c.id: c.updated_at for c in await _chapters(novel_id)}
    before |= {e.id: e.updated_at for e in await _entities(novel_id)}

    report = await _import(ArchiveTree(files), novel_id)

    assert (report.chapters_new, report.chapters_revised, report.chapters_already_current) == (
        0,
        0,
        2,
    )
    assert (
        report.entities_new,
        report.entities_revised,
        report.entities_renamed,
        report.entities_already_current,
    ) == (0, 0, 0, 2)
    assert (report.relations_created, report.relations_already_current) == (0, 1)
    assert report.conflicts == []
    assert report.metadata_conflicts == []

    after = {c.id: c.updated_at for c in await _chapters(novel_id)}
    after |= {e.id: e.updated_at for e in await _entities(novel_id)}
    assert after == before  # already current writes nothing, bumps nothing


async def test_stale_revision_is_refused(a_user: None) -> None:
    """A file older than the stock row never overwrites newer prose."""
    novel_id = await _seed_novel()
    async with Session() as session:
        chapter = await session.scalar(
            select(Chapter).where(Chapter.novel_id == novel_id, Chapter.title == "Ankunft")
        )
        assert chapter is not None
        chapter.updated_at = STALE_BASE
        await session.commit()

    _, files = await _export(novel_id)
    archive = parse_archive(ArchiveTree(files))
    stale = archive.chapters[0]  # parsed reading order: "Ankunft" is first
    assert stale.title == "Ankunft"
    stale.body = "Umgeschrieben.\n"
    stale.updated = STALE_BASE - timedelta(days=1)
    files = serialize_archive(archive)

    report = await _import(ArchiveTree(files), novel_id)

    assert report.chapters_new == 0 and report.chapters_revised == 0
    assert report.chapters_already_current == 1
    assert len(report.conflicts) == 1
    conflict = report.conflicts[0]
    assert conflict.file == "Ankunft"
    assert "stale" in conflict.reason

    fresh = await _chapters(novel_id)
    assert fresh[0].body == "Der Regen hörte auf.\n"  # byte-unchanged
    assert fresh[0].title == "Ankunft"


async def test_newer_file_revision_applies(a_user: None) -> None:
    """A file not older than the stock row revises title and body."""
    novel_id = await _seed_novel()
    async with Session() as session:
        chapter = await session.scalar(
            select(Chapter).where(Chapter.novel_id == novel_id, Chapter.title == "Ankunft")
        )
        assert chapter is not None
        chapter.updated_at = STALE_BASE
        await session.commit()

    _, files = await _export(novel_id)
    archive = parse_archive(ArchiveTree(files))
    revised = archive.chapters[0]
    revised.body = "Umgeschrieben.\n"
    revised.updated = STALE_BASE  # equal counts: not older than the row
    files = serialize_archive(archive)

    report = await _import(ArchiveTree(files), novel_id)

    assert report.chapters_revised == 1 and report.chapters_new == 0
    assert report.conflicts == []
    fresh = await _chapters(novel_id)
    assert fresh[0].body == "Umgeschrieben.\n"
    assert fresh[0].title == "Ankunft"


async def test_bare_chapter_file_imports(a_user: None) -> None:
    """A hand-dropped file with no frontmatter and no index entry imports."""
    novel_id = await _seed_novel()
    files = {
        "chapters/ein-nachtstück.md": b"Zwei Uhr nachts.\n",
        "chapters/epilog.md": b"Und war gut.\n",
    }

    report = await _import(ArchiveTree(files), novel_id)

    assert report.chapters_new == 2
    assert report.conflicts == []
    fresh = await _chapters(novel_id)
    assert [c.position for c in fresh] == [0, 1, 2, 3]  # appended after the last stock position
    assert [c.title for c in fresh[2:]] == ["ein nachtstück", "epilog"]  # filename order, stems
    assert fresh[2].body == "Zwei Uhr nachts.\n"


async def test_entity_rename_is_applied_and_reported(a_user: None) -> None:
    """An id-matched entity with a new name is renamed; its edges ride along."""
    novel_id = await _seed_novel()
    _, files = await _export(novel_id)
    archive = parse_archive(ArchiveTree(files))
    mira = next(entity for entity in archive.entities if entity.name == "Mira")
    mira.name = "Mira Winter"
    files = serialize_archive(archive)

    report = await _import(ArchiveTree(files), novel_id)

    assert report.entities_renamed == 1
    assert report.entities_revised == 0 and report.entities_new == 0

    chapters, entities, edges = await _rows(novel_id)
    assert len(chapters) == 2
    assert sorted(e.name for e in entities) == ["Mira Winter", "Émile Zola"]
    mira_row = next(e for e in entities if e.name == "Mira Winter")
    assert len(edges) == 1  # the FK edges are intact, same count
    assert edges[0].from_entity_id == mira_row.id


async def test_unknown_entity_type_is_a_conflict(a_user: None) -> None:
    """A type outside the vocabulary is a conflict; nothing is created."""
    novel_id = await _seed_novel()
    archive = NovelArchive(
        title="Der Wanderer",  # stock title: no metadata noise in this test
        entities=[
            EntityFile(name="Smaug", type="dragon", aliases=[], tags=[], body="Ein Drache.\n")
        ],
    )

    report = await _import(ArchiveTree(serialize_archive(archive)), novel_id)

    assert report.entities_new == 0
    assert len(report.conflicts) == 1
    assert report.conflicts[0].file == "Smaug"
    assert "dragon" in report.conflicts[0].reason
    _, entities, _ = await _rows(novel_id)
    assert sorted(e.name for e in entities) == ["Mira", "Émile Zola"]  # nothing created


async def test_type_discrepancy_is_a_conflict(a_user: None) -> None:
    """An id-matched entity whose type differs is skipped, not rewritten."""
    novel_id = await _seed_novel()
    _, files = await _export(novel_id)
    archive = parse_archive(ArchiveTree(files))
    mira = next(entity for entity in archive.entities if entity.name == "Mira")
    mira.type = "location"  # stock says character; everything else identical
    files = serialize_archive(archive)

    report = await _import(ArchiveTree(files), novel_id)

    assert report.entities_new == 0 and report.entities_revised == 0
    assert report.entities_renamed == 0 and report.entities_already_current == 1
    assert len(report.conflicts) == 1
    assert report.conflicts[0].file == "Mira"
    assert "type" in report.conflicts[0].reason

    _, entities, edges = await _rows(novel_id)
    mira_row = next(e for e in entities if e.name == "Mira")
    assert mira_row.type == "character"  # row unchanged
    assert mira_row.content == "Jung.\n"
    assert len(edges) == 1


async def test_edges_are_create_only(a_user: None) -> None:
    """Identical edge is already current; a note difference and an absent
    target are conflicts; nothing is ever rewritten or silently dropped."""
    novel_id = await _seed_novel()
    archive = NovelArchive(
        title="Der Wanderer",
        # One already-current entity keeps the archive non-empty (an archive
        # with no chapters and no entities refuses outright).
        entities=[
            EntityFile(
                name="Mira",
                type="character",
                aliases=["Die Wanderin"],
                tags=["protagonist"],
                body="Jung.\n",
            )
        ],
        relations=[
            RelationEdge(
                from_name="Mira", relation_type="knows", to_name="Émile Zola", note="aus Briefen"
            ),
            RelationEdge(
                from_name="Mira", relation_type="knows", to_name="Émile Zola", note="ANDERS"
            ),
            RelationEdge(from_name="Émile Zola", relation_type="mentors", to_name="Caspar"),
        ],
    )

    report = await _import(ArchiveTree(serialize_archive(archive)), novel_id)

    assert report.entities_already_current == 1
    assert (report.relations_created, report.relations_already_current) == (0, 1)
    assert len(report.conflicts) == 2
    reasons = [c.reason for c in report.conflicts]
    assert any("ANDERS" in reason or "note" in reason for reason in reasons)
    absent = next(c for c in report.conflicts if "mentors" in c.file)
    assert absent.file == "Émile Zola -mentors-> Caspar"  # the conflict names the edge

    _, _, edges = await _rows(novel_id)
    assert len(edges) == 1  # nothing created
    assert edges[0].note == "aus Briefen"  # never an unguarded overwrite


async def test_merge_does_not_touch_novel_metadata(a_user: None) -> None:
    """On merge, differing metadata fields are reported and never applied."""
    novel_id = await _seed_novel()
    archive = NovelArchive(
        title="Anderer Titel",
        genre="Sci-Fi",
        chapters=[ChapterFile(title="Ankunft", position=0, body="Der Regen hörte auf.\n")],
    )

    report = await _import(ArchiveTree(serialize_archive(archive)), novel_id)

    assert report.metadata_conflicts == ["title", "genre"]
    assert [c.file for c in report.conflicts if c.file == "metadata.json"] == [
        "metadata.json",
        "metadata.json",
    ]
    novel = await _novel_row(novel_id)
    assert novel.title == "Der Wanderer"  # the row is unchanged
    assert novel.genre == "Fantasy"  # the archive's "Sci-Fi" was not applied
    assert novel.author == "E. A. Guest"
    assert report.chapters_new == 1  # the archive's one chapter still imports (no id)


async def test_new_novel_applies_metadata(a_user: None) -> None:
    """The new-novel path applies title, author, genre, blurb and language."""
    archive = NovelArchive(
        title="Dead Signal",
        author="J. Autorin",
        genre="Sci-Fi",
        blurb="Ein Signal ohne Absender.",
        language="en",
        chapters=[ChapterFile(title="Ankunft", position=1, body="Das Quellen band.\n")],
        entities=[EntityFile(name="Vega", type="location", aliases=[], tags=[], body="Station.\n")],
    )

    report = await _import(ArchiveTree(serialize_archive(archive)), None)

    novel = await _novel_row(report.novel_id)
    assert novel.title == "Dead Signal"
    assert novel.author == "J. Autorin"
    assert novel.genre == "Sci-Fi"
    assert novel.blurb == "Ein Signal ohne Absender."
    assert novel.language == "en"
    assert report.chapters_new == 1 and report.entities_new == 1
    assert report.conflicts == []


async def test_import_maintains_search_text_and_embedding(a_user: None) -> None:
    """New and content-changed entities carry search_text and the vector;
    an already-current entity is untouched, sentinel embedding and all."""
    novel_id = await _seed_novel()
    sentinel = [0.5] * 384
    async with Session() as session:
        mira = await session.scalar(
            select(Entity).where(Entity.novel_id == novel_id, Entity.name == "Mira")
        )
        assert mira is not None
        mira.embedding = sentinel
        mira.search_text = "sentinel"
        await session.commit()
    mira_updated_at = next(
        entity for entity in await _entities(novel_id) if entity.name == "Mira"
    ).updated_at

    _, files = await _export(novel_id)
    archive = parse_archive(ArchiveTree(files))
    archive.entities.append(
        EntityFile(
            name="Caspar", type="location", aliases=["Der See"], tags=["ort"], body="Ein See.\n"
        )
    )
    emile = next(entity for entity in archive.entities if entity.name == "Émile Zola")
    emile.body = "Schriftsteller und Mentor.\n"
    report = await _import(ArchiveTree(serialize_archive(archive)), novel_id)

    assert (report.entities_new, report.entities_revised, report.entities_already_current) == (
        1,
        1,
        1,
    )
    assert report.relations_already_current == 1

    _, entities, _ = await _rows(novel_id)
    by_name = {e.name: e for e in entities}
    fake = FakeEmbeddingProvider()

    caspar = by_name["Caspar"]
    assert caspar.search_text == "Caspar Der See ort"
    [expected] = await fake.embed(["Caspar Der See ort Ein See.\n"])
    assert caspar.embedding is not None
    assert caspar.embedding == pytest.approx(expected)
    assert len(caspar.embedding) == 384

    emile_row = by_name["Émile Zola"]
    assert emile_row.search_text == "Émile Zola"
    [expected] = await fake.embed(["Émile Zola Schriftsteller und Mentor.\n"])
    assert emile_row.embedding is not None
    assert emile_row.embedding == pytest.approx(expected)

    mira_row = by_name["Mira"]
    assert mira_row.embedding is not None
    assert list(mira_row.embedding) == sentinel  # untouched
    assert mira_row.search_text == "sentinel"
    assert mira_row.updated_at == mira_updated_at


async def test_empty_archive_is_refused(a_user: None) -> None:
    """A `zip -r` envelope — directories, no chapters, no entities — refuses
    on both paths instead of merging as a silent 0/0 success."""
    novel_id = await _seed_novel()
    envelope = ArchiveTree(
        {
            "metadata.json": '{"title": "Leere Hülle"}\n'.encode(),
            "chapters/.keep": b"",
            "kb/.keep": b"",
        }
    )

    with pytest.raises(ArchiveError):
        await _import(envelope, None)
    with pytest.raises(ArchiveError):
        await _import(envelope, novel_id)

    assert await _novel_count() == 1  # the refused new-novel path created nothing
    chapters, entities, _ = await _rows(novel_id)
    assert len(chapters) == 2 and len(entities) == 2
