"""First-run shapes: is the instance set up, and the one call that sets it up."""

from typing import Literal
from uuid import UUID  # noqa: TC003  Pydantic resolves annotations at runtime

from pydantic import BaseModel, Field, field_validator

from app.kernel.interchange.demos import DEMO_SLUGS


class SetupStatus(BaseModel):
    complete: bool


class SetupRequest(BaseModel):
    novel_title: str = Field(min_length=1, max_length=200)
    # A demo slug imports that bundled archive instead of the blank novel.
    # A value outside the bundled slugs is refused as a 422 naming this field.
    demo: str | None = None
    # The wizard's per-novel answers, all optional. The enum vocabularies are
    # the Stitch drafts' radio values; ``dramatic_form`` stays a free string
    # until the template wave pins its vocabulary. A demo's own genre wins
    # over ``genre`` (the service keeps the archive's identity).
    genre: str | None = Field(default=None, max_length=80)
    # The ceiling is the Integer column's own (2**31 - 1): a larger goal is a
    # 422 here, not an int32 overflow at the insert.
    target_words: int | None = Field(default=None, ge=1, le=2_147_483_647)
    author_typology: Literal["plotter", "pantser", "plantser"] | None = None
    dramatic_form: str | None = Field(default=None, max_length=80)
    ai_role: Literal["archivar", "coautor", "lektor", "sparring"] | None = None
    canon_strictness: int | None = Field(default=None, ge=1, le=5)

    @field_validator("demo")
    @classmethod
    def demo_must_be_bundled(cls, value: str | None) -> str | None:
        if value is not None and value not in DEMO_SLUGS:
            raise ValueError(f"unknown demo: {value!r} is not one of the bundled demos")
        return value


class SetupResult(BaseModel):
    novel_id: UUID
    novel_title: str
