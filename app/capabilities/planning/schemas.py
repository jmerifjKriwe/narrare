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
