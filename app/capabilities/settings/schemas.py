"""The settings payloads: the language, the provider profiles, the assignments.

``None`` on the locale means "follow the browser". On a profile update, an
``api_key`` that is absent or empty means "keep the stored one" — clearing a
key is not an operation, only replacing it is. Every read of a profile shows
the mask (``sk-…`` plus the last four characters), never the key: the one
response that carries the full key is the create's, once (design §Masked
keys).
"""

from datetime import datetime  # noqa: TC003  Pydantic resolves these at runtime
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, Field, field_validator

from app.generated.locales import LOCALES
from app.kernel.llm.models import PROFILE_KINDS


class SettingsRead(BaseModel):
    locale: str | None


class SettingsUpdate(BaseModel):
    # Present and nullable, deliberately: ``{"locale": null}`` hands the choice
    # back to the browser, while ``{}`` is a client bug and must not mean the
    # same thing. A field with a default could not tell the two apart.
    locale: str | None

    @field_validator("locale")
    @classmethod
    def _carried_by_the_catalog(cls, value: str | None) -> str | None:
        # The catalog's filenames are the list of languages; a code outside it
        # would render an untranslated page and hide the mistake.
        if value is not None and value not in LOCALES:
            known = ", ".join(LOCALES)
            raise ValueError(f"unknown locale {value!r}; the catalog carries {known}")
        return value


class ProfileCreate(BaseModel):
    """One new provider profile. ``api_key`` is write-only; the mask comes back."""

    name: str = Field(min_length=1, max_length=120)
    kind: str
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    api_key: str | None = None
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0, le=2)
    request_timeout: float | None = Field(default=None, gt=0)

    @field_validator("kind")
    @classmethod
    def _kind_is_in_the_vocabulary(cls, value: str) -> str:
        # A closed vocabulary in code, like ENTITY_TYPES; a typo must fail at
        # the gate, not at the first call that resolves the profile.
        if value not in PROFILE_KINDS:
            known = "|".join(PROFILE_KINDS)
            raise ValueError(f"unknown profile kind {value!r}; known: {known}")
        return value


class ProfileUpdate(BaseModel):
    """What a patch may change. The kind is what the profile is: not editable.

    Absent fields stay unchanged; present nulls clear the nullable columns.
    ``is_default: true`` hands the default over from the current holder.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    api_key: str | None = None
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0, le=2)
    request_timeout: float | None = Field(default=None, gt=0)
    is_default: bool | None = None


class ProfileRead(BaseModel):
    """A profile as every read shows it: the mask, never the key."""

    id: UUID
    name: str
    kind: str
    base_url: str | None
    model: str | None
    api_key_mask: str | None
    is_default: bool
    context_window: int | None
    max_output_tokens: int | None
    temperature: float | None
    request_timeout: float | None
    created_at: datetime
    updated_at: datetime


class ProfileCreated(ProfileRead):
    """The create's answer: the one response that carries the full key.

    ``api_key`` is the plaintext exactly once, for the client that just sent
    it to confirm against; it is ``None`` when no key was stored (a fake, or
    a local endpoint without one).
    """

    api_key: str | None = None


class ProfileTestResult(BaseModel):
    """What one connection test found: it ran, and it either answered or named why."""

    ok: bool
    error: str | None
    latency_ms: int


class AssignmentUpdate(BaseModel):
    """``profile_id: null`` clears the task's assignment (back down the cascade)."""

    profile_id: UUID | None


class AssignmentRead(BaseModel):
    task_key: str
    profile_id: UUID | None


class TaskEffectiveRead(BaseModel):
    """One known task key and the tier that actually serves it.

    ``profile_id`` and ``profile_name`` are ``None`` exactly when no profile
    serves — the environment tier answers. ``kind`` names the serving adapter
    either way (``fake`` or ``openai-chat``), so the page can say what answers
    without claiming the cascade's stored choice. An audit-only key has no
    serving tier: ``kind`` is ``audit``, the profile fields are ``None``, and
    ``assignable`` is ``False``.
    """

    task_key: str
    profile_id: UUID | None
    profile_name: str | None
    kind: str
    assignable: bool
