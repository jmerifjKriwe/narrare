"""First-run shapes: is the instance set up, and the one call that sets it up."""

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

    @field_validator("demo")
    @classmethod
    def demo_must_be_bundled(cls, value: str | None) -> str | None:
        if value is not None and value not in DEMO_SLUGS:
            raise ValueError(f"unknown demo: {value!r} is not one of the bundled demos")
        return value


class SetupResult(BaseModel):
    novel_id: UUID
    novel_title: str
