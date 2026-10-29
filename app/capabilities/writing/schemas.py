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
    created_at: datetime
    updated_at: datetime


class ChapterCreate(BaseModel):
    # Empty is the honest default: the database stores no locale, the chapter
    # list shows the localized placeholder for an untitled chapter.
    title: str = Field(default="", max_length=200)


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None


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
