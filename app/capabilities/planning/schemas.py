"""Request and response shapes for scene-plan aggregates."""

from datetime import datetime  # noqa: TC003  Pydantic resolves these at runtime
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class PlanningErrorRead(BaseModel):
    """The JSON body for a missing chapter aggregate or a refused PUT."""

    detail: str


class SceneUpsert(BaseModel):
    """One scene of the PUT aggregate, by stable id.

    New scenes carry client-generated ids — the diff treats an id the
    chapter does not know and nobody else owns as a creation. The body
    carries no timestamps: those are the server's own.
    """

    id: UUID
    # Empty is the honest default, the chapters' rule: the dock's list shows
    # its own placeholder for an untitled scene. The length is the schema's
    # one refusal.
    title: str = Field(max_length=200)
    purpose: str = ""
    conflict: str = ""
    resolution: str = ""
    beats: list[str] = Field(default_factory=list[str])
    status: str = "planned"


class SceneAggregateUpdate(BaseModel):
    """The PUT body: the chapter's whole scene list, in its new order."""

    scenes: list[SceneUpsert] = Field(default_factory=list[SceneUpsert])


class SceneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chapter_id: UUID
    position: int
    title: str
    purpose: str
    conflict: str
    resolution: str
    beats: list[str]
    status: str
    created_at: datetime
    updated_at: datetime


class SceneAggregateRead(BaseModel):
    """The chapter's scenes in position order, with the version the dock
    compares its snapshot against: the chapter's own stamp, touched by
    every aggregate write."""

    chapter_id: UUID
    scenes: list[SceneRead]
    version_updated_at: datetime


class TimelineEventCreate(BaseModel):
    """The POST body: one event on the novel's timeline.

    The body carries no timestamps: those are the server's own. ``position``
    is the manual order (null leaves the event unordered, listed last);
    ``date_label`` is the optional free-text date; ``character_names`` are
    free-text names for now — no KB linkage in this slice.
    """

    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    chapter_id: UUID | None = None
    position: int | None = None
    date_label: str = Field(default="", max_length=200)
    character_names: list[str] = Field(default_factory=list[str])


class TimelineEventUpdate(BaseModel):
    """The PUT body: only the fields present are the change.

    A carried ``null`` clears ``chapter_id`` or ``position``; an absent
    field leaves it alone. Every other field is non-nullable — a carried
    null is a 422 at the boundary, never a NOT NULL violation on write.
    A blank title is refused, never stored.
    """

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str = ""
    chapter_id: UUID | None = None
    position: int | None = None
    date_label: str = Field(default="", max_length=200)
    character_names: list[str] = Field(default_factory=list[str])


class TimelineEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    chapter_id: UUID | None
    title: str
    description: str
    position: int | None
    date_label: str
    character_names: list[str]
    created_at: datetime
    updated_at: datetime
