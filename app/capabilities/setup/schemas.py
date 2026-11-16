"""First-run shapes: is the instance set up, and the one call that sets it up."""

from uuid import UUID  # noqa: TC003  Pydantic resolves annotations at runtime

from pydantic import BaseModel, Field, field_validator

from app.kernel.contracts.models import (
    AI_ROLES,
    AUTHOR_TYPOLOGIES,
    CANON_STRICTNESS_MAX,
    CANON_STRICTNESS_MIN,
    DRAMATIC_FORM_MAX_LENGTH,
    WORD_GOAL_MAX,
    WORD_GOAL_MIN,
)
from app.kernel.interchange.demos import DEMO_SLUGS


class SetupStatus(BaseModel):
    complete: bool


class SetupRequest(BaseModel):
    novel_title: str = Field(min_length=1, max_length=200)
    # A demo slug imports that bundled archive instead of the blank novel.
    # A value outside the bundled slugs is refused as a 422 naming this field.
    demo: str | None = None
    # The wizard's per-novel answers, all optional. The vocabularies and
    # bounds are the kernel contract's shared constants (the Stitch drafts'
    # radio values) — writing's novel update validates against the same home;
    # ``dramatic_form`` stays a free string until the template wave pins its
    # vocabulary. A demo's own genre wins over ``genre`` (the service keeps
    # the archive's identity).
    genre: str | None = Field(default=None, max_length=80)
    # The ceiling is the Integer column's own (WORD_GOAL_MAX): a larger goal
    # is a 422 here, not an int32 overflow at the insert.
    target_words: int | None = Field(default=None, ge=WORD_GOAL_MIN, le=WORD_GOAL_MAX)
    author_typology: str | None = None
    dramatic_form: str | None = Field(default=None, max_length=DRAMATIC_FORM_MAX_LENGTH)
    ai_role: str | None = None
    canon_strictness: int | None = Field(
        default=None, ge=CANON_STRICTNESS_MIN, le=CANON_STRICTNESS_MAX
    )

    @field_validator("demo")
    @classmethod
    def demo_must_be_bundled(cls, value: str | None) -> str | None:
        if value is not None and value not in DEMO_SLUGS:
            raise ValueError(f"unknown demo: {value!r} is not one of the bundled demos")
        return value

    @field_validator("author_typology")
    @classmethod
    def _typology_is_in_the_vocabulary(cls, value: str | None) -> str | None:
        # A closed vocabulary in code, like PROVIDER_KINDS: a typo must fail
        # at the gate, naming this field, not land on the novel's row.
        if value is not None and value not in AUTHOR_TYPOLOGIES:
            known = "|".join(AUTHOR_TYPOLOGIES)
            raise ValueError(f"unknown author_typology {value!r}; known: {known}")
        return value

    @field_validator("ai_role")
    @classmethod
    def _role_is_in_the_vocabulary(cls, value: str | None) -> str | None:
        if value is not None and value not in AI_ROLES:
            known = "|".join(AI_ROLES)
            raise ValueError(f"unknown ai_role {value!r}; known: {known}")
        return value


class SetupResult(BaseModel):
    """The provisioning facts step 4 and the landing render.

    ``genre`` is the effective genre — the archive's own on the demo path,
    the passed genre on the blank path — and ``chapters`` the count the
    import/creation produced. The settings are nullable as the model is:
    a novel without an answer does not lie.
    """

    novel_id: UUID
    novel_title: str
    genre: str | None
    target_words: int | None
    author_typology: str | None
    dramatic_form: str | None
    ai_role: str | None
    canon_strictness: int | None
    chapters: int
