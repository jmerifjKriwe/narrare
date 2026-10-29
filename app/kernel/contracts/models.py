"""Shared domain vocabulary. Two capabilities need these, so they live here."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import Base, UserOwned

ENTITY_TYPES = (
    "character",
    "location",
    "faction",
    "object",
    "system",
    "timeline",
    "event",
    "generic",
)
"""The extraction contract's closed vocabulary. A short tuple in code, not a
PG enum and not a table: the set is fixed by the prompt, not by data, and
every consumer — prompts, parse, service validation, panel labels — imports
it from here."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    # NULL means "follow the browser": a user who never chose has no opinion,
    # and the client decides from navigator.languages. A tag the catalog does
    # not carry is refused at the API, not stored.
    locale: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Novel(UserOwned):
    __tablename__ = "novels"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str | None] = mapped_column(String(80))
    blurb: Mapped[str | None] = mapped_column(Text)
    # The export's front matter. The language is a BCP-47-ish code (`de`,
    # `en`); both are nullable — a novel without an answer does not lie.
    author: Mapped[str | None] = mapped_column(String(200))
    language: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Chapter(UserOwned):
    __tablename__ = "chapters"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int]
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Entity(UserOwned):
    """An entity the user kept: one thing of the story, with its type, its
    other names, its tags and its Markdown body.

    Born only through review — an accepted :class:`EntitySuggestion` creates
    it — so the table holds the story's canon, not the model's proposals.
    ``search_text`` is the maintained concatenation the trigram search runs
    over (name, aliases, tags); it is written by the same paths that write
    those fields, never by the client.
    """

    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    # One of ENTITY_TYPES. A short string, not an enum type: the set is
    # fixed by the prompt, not by data.
    type: Mapped[str] = mapped_column(String(40))
    # The body, stored as Markdown from WP1 on (D2): edited and shown as
    # plain source; WP3 makes Markdown canonical.
    content: Mapped[str] = mapped_column(Text, default="")
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # name + aliases + tags, maintained by the write paths; the `q` tier
    # searches this column with word_similarity, so the GIN trigram index
    # below is what keeps it off a sequential scan.
    search_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index(
            "ix_entities_search_text",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )


class EntityRelation(UserOwned):
    """One directed edge between two of the story's entities.

    ``relation_type`` is free text — the suggested vocabulary is a UI
    autocomplete, not an API constraint (D7) — and the ends are immutable:
    moving an edge is delete plus create. The unique constraint is the
    duplicate rule a merge's re-pointing folds under; both foreign keys
    cascade, so a delete takes its edges along (D4).
    """

    __tablename__ = "entity_relations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    from_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    to_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "from_entity_id",
            "to_entity_id",
            "relation_type",
            name="uq_entity_relations_edge",
        ),
    )


class EntitySuggestion(UserOwned):
    """One entity the provider proposed for a chapter, awaiting review.

    The review contract: born ``pending``, consumed exactly once — accept
    turns it into an :class:`Entity`, discard drops it. The state transition
    is the consuming side's to guard, in one transaction.
    """

    __tablename__ = "entity_suggestions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    # One of ENTITY_TYPES.
    type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    # The proposed relations, as a JSON column — no child table. Written as
    # [] until extraction v2 fills it (Task 2); accept resolves it.
    relations: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)
    # pending | accepted | discarded — the review contract's three states.
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ConsistencyFinding(UserOwned):
    """One contradiction the whole-novel check found, awaiting review.

    The review contract mirrors the suggestion queue's: born ``pending``,
    consumed exactly once — acknowledged (seen; the text stays as it is) or
    dismissed. ``summary`` is the finding's identity: a re-run of the check
    files nothing new while the same summary is still pending.
    """

    __tablename__ = "consistency_findings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    summary: Mapped[str] = mapped_column(String(200))
    # The quoted readings that disagree, when the provider offered them.
    detail: Mapped[str | None] = mapped_column(Text)
    # pending | acknowledged | dismissed — the review contract's three states.
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Document(UserOwned):
    """An uploaded text the knowledge base can search."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    # The width the configured model answered with at ingest time. All of one
    # user's documents share it — the corpus guard refuses a mix — because
    # vectors from two models are not comparable.
    embedding_width: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Chunk(UserOwned):
    """A passage of a document, with its embedding."""

    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    position: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
