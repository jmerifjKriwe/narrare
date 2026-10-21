"""First-run shapes: is the instance set up, and the one call that sets it up."""

from uuid import UUID  # noqa: TC003  Pydantic resolves annotations at runtime

from pydantic import BaseModel, Field


class SetupStatus(BaseModel):
    complete: bool


class SetupRequest(BaseModel):
    novel_title: str = Field(min_length=1, max_length=200)


class SetupResult(BaseModel):
    novel_id: UUID
    novel_title: str
