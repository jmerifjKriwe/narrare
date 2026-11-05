"""Request and response shapes for the writing capability."""

from datetime import datetime  # noqa: TC003  Pydantic resolves these at runtime
from typing import Literal
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class WritingErrorRead(BaseModel):
    """The JSON body for missing resources and incomplete setup."""

    detail: str


class NovelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    genre: str | None = Field(default=None, max_length=80)
    blurb: str | None = None


class NovelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    genre: str | None
    blurb: str | None
    author: str | None
    language: str | None
    # Derived, not stored: how long the novel is, counted from its
    # chapters — a chapter per row, a word per whitespace-separated
    # token of the trimmed body, an empty body worth nothing. The
    # defaults keep a novel with no chapters at zeros and old clients
    # reading the grown payload unbroken.
    chapter_count: int = 0
    word_count: int = 0
    created_at: datetime
    updated_at: datetime
    # The export's trace: set by every successful export and by nothing
    # else, so a metadata edit leaves it honestly stale — None until the
    # first export reads it.
    last_exported_at: datetime | None


class NovelUpdate(BaseModel):
    """The PATCH body: only the fields present are the change.

    ``None`` is ambiguous by shape alone — an absent field and a cleared
    author both look like None — so the service reads
    ``model_fields_set`` to tell a carried change from a missing one. The
    values are checked there, against the novel contract's trims and
    limits: this schema carries the fields, the contract decides what a
    value may be. A carried ``null`` clears author, genre, blurb or
    language; the title is never clearable.
    """

    title: str | None = None
    genre: str | None = None
    blurb: str | None = None
    author: str | None = None
    language: str | None = None


class ChapterCreate(BaseModel):
    # Empty is the honest default: the database stores no locale, the chapter
    # list shows the localized placeholder for an untitled chapter.
    title: str = Field(default="", max_length=200)


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None


class ChapterOrderUpdate(BaseModel):
    """The PUT chapter-order body: the whole rail, in its new order.

    Every chapter of the novel and nothing else — an arrangement is a
    permutation of the ids the book holds this moment, so the service
    compares the body against the stored set as one whole and refuses a
    stale one (a second tab's add, delete or repeat) with the current
    order, rather than reshape what the writer no longer sees.
    """

    chapter_ids: list[UUID]


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    title: str
    position: int
    body: str
    created_at: datetime
    updated_at: datetime


class ExportRequest(BaseModel):
    """One export: into a directory on disk, or as a ZIP download."""

    mode: Literal["path", "zip"]
    path: str | None = None


class ExportDone(BaseModel):
    """The receipt of a path export: where it went and how much."""

    path: str
    chapters: int
    entities: int


class ConflictRead(BaseModel):
    """One item the merge rules refused: which archive file, and why.

    `file` carries the archive-side path the parse stamped on the item —
    untrusted text, a plain string by contract. `code` is the stable key the
    receipt localizes, with `params` interpolated; `reason` is the technical
    detail, and the fallback for a code the client does not know.
    """

    model_config = ConfigDict(from_attributes=True)

    file: str
    reason: str
    code: str
    params: dict[str, str]


class ImportReportRead(BaseModel):
    """What one import did, per class — the engine's report, field by field.

    Every matched item lands in exactly one of new / revised / renamed /
    already_current; an item a conflict refused increments nothing.
    """

    model_config = ConfigDict(from_attributes=True)

    novel_id: UUID
    chapters_new: int
    chapters_revised: int
    chapters_already_current: int
    entities_new: int
    entities_revised: int
    entities_renamed: int
    entities_already_current: int
    relations_created: int
    relations_already_current: int
    conflicts: list[ConflictRead]
    metadata_conflicts: list[str]


class FieldRefusalRead(BaseModel):
    """One refused field inside a 422 body — `loc` names the request part."""

    loc: list[str]
    msg: str
    type: str


class FieldRefusalsRead(BaseModel):
    """The 422 body when the request breaks a field contract."""

    detail: list[FieldRefusalRead]


class ArchiveInvalidRead(BaseModel):
    """The 422 detail when the archive itself is unreadable or malformed."""

    code: Literal["archive_invalid"]
    file: str
    reason: str


class ImportRefusalsRead(BaseModel):
    """The import's 422 body: a refused field, or the offending archive file."""

    detail: list[FieldRefusalRead] | ArchiveInvalidRead
