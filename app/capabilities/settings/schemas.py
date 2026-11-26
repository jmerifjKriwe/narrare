"""The settings payloads: the language, the theme, the profile, the
providers, the models, the assignments.

``None`` on the locale means "follow the browser"; on the author name it
falls back to the email label, and on the daily goal it means no goal. On a
provider update, an ``api_key`` that is absent or empty means "keep the
stored one" — clearing a key is not an operation, only replacing it is.
Every read of a provider shows the mask (``sk-…`` plus the last four
characters), never the key: the one response that carries the full key is
the provider create's, once (design §Masked keys). A model carries no key at
all — it names a provider, and the provider holds the secret.
"""

from datetime import datetime  # noqa: TC003  Pydantic resolves these at runtime
from typing import Literal
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, Field, field_validator

from app.generated.locales import LOCALES
from app.kernel.contracts.models import WORD_GOAL_MAX, WORD_GOAL_MIN
from app.kernel.llm.models import (
    CUSTOM_OUTPUT_PROFILE,
    OUTPUT_PROFILE_CUSTOM_MAX,
    OUTPUT_PROFILES,
    PROVIDER_KINDS,
)
from app.kernel.llm.resolution import OutputProfile


class SettingsRead(BaseModel):
    locale: str | None
    theme: str | None
    # The profile's answers (W4 D9/D22, D8): the user block's label and the
    # atelier's daily goal. None is the honest unset — the email label and
    # no goal — never a guessed value.
    author_name: str | None
    daily_goal_words: int | None
    # The update check's interval (design 2026-11-24): the user's answer, seven
    # days by default. None only when the instance is uninstalled — an installed
    # row always carries the product default.
    update_check_interval_days: int | None
    # The row's own email (W4 Task 10): the user block's fallback label when
    # no author name is stored. Read-only — the preference write carries no
    # email; the local instance's row may hold none, and None is the honest
    # answer then.
    email: str | None


class SettingsUpdate(BaseModel):
    # Present and nullable, deliberately: ``{"locale": null}`` hands the choice
    # back to the browser, while ``{}`` is a client bug and must not mean the
    # same thing. A field with a default could not tell the two apart. The
    # width is the column's own (String(64)) — the registry's longest code.
    locale: str | None = Field(max_length=64)
    # The profile fields (W4) are present-and-nullable through
    # ``model_fields_set``, the novel update's rule: an absent field keeps the
    # stored answer — the language switchers carry the locale alone — while a
    # carried ``null`` clears it, the author name back to the email label and
    # the daily goal back to no goal. Absent and null are different answers.
    author_name: str | None = None
    # A goal counts from one; the ceiling is the Integer column's own
    # (WORD_GOAL_MAX), a 422 here rather than an overflow at the write.
    daily_goal_words: int | None = Field(default=None, ge=WORD_GOAL_MIN, le=WORD_GOAL_MAX)
    # The update check's interval, partial like the profile fields: absent keeps
    # the stored answer, a carried ``None`` resets to the product default (7).
    # One day is the shortest useful interval and a year the longest.
    update_check_interval_days: int | None = Field(default=None, ge=1, le=365)

    @field_validator("locale")
    @classmethod
    def _carried_by_the_catalog(cls, value: str | None) -> str | None:
        # The catalog's filenames are the list of languages; a code outside it
        # would render an untranslated page and hide the mistake.
        if value is not None and value not in LOCALES:
            known = ", ".join(LOCALES)
            raise ValueError(f"unknown locale {value!r}; the catalog carries {known}")
        return value

    @field_validator("author_name")
    @classmethod
    def _trimmed_and_bounded(cls, value: str | None) -> str | None:
        # The user block's label, trimmed like the novel's author:
        # whitespace-only is the honest unset (the email label answers),
        # and the width is the column's own (String(200)).
        name = (value or "").strip() or None
        if name is not None and len(name) > 200:
            raise ValueError("author_name is at most 200 characters")
        return name


THEMES: tuple[str, ...] = ("light", "dark")


class SettingsThemeRead(BaseModel):
    theme: str | None


class SettingsThemeUpdate(BaseModel):
    # Present and nullable for the same reason as the locale: ``{"theme": null}``
    # hands the choice back to the system, while ``{}`` is a client bug.
    theme: str | None

    @field_validator("theme")
    @classmethod
    def _one_of_the_two(cls, value: str | None) -> str | None:
        if value is not None and value not in THEMES:
            known = ", ".join(THEMES)
            raise ValueError(f"unknown theme {value!r}; the app carries {known}")
        return value


class ModelCreate(BaseModel):
    """One new model under one of the user's providers.

    The provider is named, not repeated: kind, endpoint and key live there.
    The service's gate refuses a ``provider_id`` that is not the user's —
    the schema cannot know ownership, only shape.
    """

    name: str = Field(min_length=1, max_length=120)
    provider_id: UUID
    model: str = Field(min_length=1, max_length=200)
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0, le=2)
    request_timeout: float | None = Field(default=None, gt=0)


class ModelUpdate(BaseModel):
    """What a patch may change. The provider and the model string can move.

    Absent fields stay unchanged; present nulls clear the tunables. Clearing
    the name, the provider or the model string is refused by the service —
    a model without one of them is not a configuration. ``is_default: true``
    hands the default over from the current holder.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider_id: UUID | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0, le=2)
    request_timeout: float | None = Field(default=None, gt=0)
    is_default: bool | None = None


class ModelRead(BaseModel):
    """A model as every read shows it: its provider named, no key anywhere.

    The key and its mask live on the provider; the model carries none. The
    four state fields are the settings row's marks, read-only facts:
    ``in_catalog`` is the resolution lookup's own answer (:func:`effective_info`
    with the provider's vendor — no second lookup path), and the
    ``last_error_*`` pair is the model's newest audit row, kept only when that
    call failed, so a later success clears the mark. ``catalog_max_output_tokens``
    is that same lookup's own output ceiling for the model string — beside,
    never merged into, the model's stored ``max_output_tokens``, whose column
    keeps its own meaning (the one ceiling a custom choice is bounded by).
    """

    id: UUID
    name: str
    provider_id: UUID
    provider_name: str
    model: str
    is_default: bool
    context_window: int | None
    max_output_tokens: int | None
    catalog_max_output_tokens: int | None
    temperature: float | None
    request_timeout: float | None
    in_catalog: bool
    last_error_code: str | None
    last_error_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProviderCreate(BaseModel):
    """One new provider: the saved endpoint its models hang off.

    ``api_key`` is write-only; the mask comes back.
    """

    name: str = Field(min_length=1, max_length=120)
    kind: str
    base_url: str | None = Field(default=None, max_length=500)
    models_url: str | None = Field(default=None, max_length=500)
    vendor: str | None = Field(default=None, max_length=40)
    api_key: str | None = None

    @field_validator("kind")
    @classmethod
    def _kind_is_in_the_vocabulary(cls, value: str) -> str:
        # A closed vocabulary in code, like ENTITY_TYPES; a typo must fail at
        # the gate, not at the first call that resolves the provider.
        if value not in PROVIDER_KINDS:
            known = "|".join(PROVIDER_KINDS)
            raise ValueError(f"unknown provider kind {value!r}; known: {known}")
        return value


class ProviderUpdate(BaseModel):
    """What a patch may change. The kind is what the provider is: not editable.

    Absent fields stay unchanged; present nulls clear the nullable columns.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)
    models_url: str | None = Field(default=None, max_length=500)
    vendor: str | None = Field(default=None, max_length=40)
    api_key: str | None = None


class ProviderRead(BaseModel):
    """A provider as every read shows it: the mask, never the key."""

    id: UUID
    name: str
    kind: str
    base_url: str | None
    models_url: str | None
    vendor: str | None
    api_key_mask: str | None


class ProviderCreated(ProviderRead):
    """The create's answer: the one response that carries the full key.

    ``api_key`` is the plaintext exactly once, for the client that just sent
    it to confirm against; it is ``None`` when no key was stored (a fake, or
    a local endpoint without one).
    """

    api_key: str | None = None


class PresetRead(BaseModel):
    """One provider preset as the create form reads it, with the catalog join.

    The preset is the kernel table's row — label, model and vendor are the
    vendors' proper spellings, data rather than catalog text. ``models`` is
    the vendor's catalog vocabulary, bare and sorted, the model picker's
    list; a vendor the catalog does not carry joins to an empty list and the
    form still saves free text. ``snapshot_date`` is the catalog's own date,
    ``None`` when the snapshot names none — the picker's honesty mark rides
    this response, so the form needs no second call.
    """

    id: str
    label: str
    kind: str
    base_url: str
    models_url: str | None
    vendor: str
    model: str
    note_key: str | None
    models: list[str]
    snapshot_date: str | None


class ModelTestResult(BaseModel):
    """What one connection test found: it ran, and it either answered or named why."""

    ok: bool
    error: str | None
    latency_ms: int


class AssignmentUpdate(BaseModel):
    """``profile_id: null`` clears the task's assignment (back down the cascade).

    ``output_profile`` is the task's output-length choice (W8): a vocabulary
    name (:data:`OUTPUT_PROFILES`) or an explicit number — the number *is*
    the custom profile's carrier, there is no ``"custom"`` string. Absent
    and carried null both mean ``balanced``: the profile column has no
    two-state semantics, so a save that omits the field states ``balanced``
    by that fact. A custom number above the assigned model's stored
    ``max_output_tokens`` is refused by the service's gate (422 naming the
    field); with no stored ceiling nothing bounds it.
    """

    profile_id: UUID | None
    output_profile: str | int | None = None

    @field_validator("output_profile", mode="before")
    @classmethod
    def _a_name_of_the_vocabulary_or_an_explicit_number(cls, value: object) -> object:
        # Before the union's coercion: a bool would otherwise arrive as 1 and
        # pass for the custom number 1 — a truth value is no token count.
        if value is None:
            return None
        if isinstance(value, str):
            # A str must name the vocabulary; "custom" is not a name — the
            # number itself rides instead.
            if value == CUSTOM_OUTPUT_PROFILE:
                raise ValueError("the custom output profile rides as its number, not as a name")
            if value not in OUTPUT_PROFILES:
                known = ", ".join(OUTPUT_PROFILES)
                raise ValueError(
                    f"unknown output profile {value!r}; known: {known},"
                    " or a custom token count as a number"
                )
            return value
        if isinstance(value, bool):
            raise ValueError("a token count is a whole number, not a flag")
        if isinstance(value, int):
            if not (1 <= value <= OUTPUT_PROFILE_CUSTOM_MAX):
                raise ValueError(
                    "a custom output profile is a token count between 1 and"
                    f" {OUTPUT_PROFILE_CUSTOM_MAX}"
                )
            return value
        raise ValueError(
            "an output profile is a vocabulary name or a custom token count as a number"
        )

    def output_choice(self) -> OutputProfile | None:
        """The carried choice as the kernel's type; ``None`` means no choice."""
        if self.output_profile is None:
            return None
        if isinstance(self.output_profile, int):
            return OutputProfile(name=CUSTOM_OUTPUT_PROFILE, custom=self.output_profile)
        return OutputProfile(name=self.output_profile)


class AssignmentRead(BaseModel):
    """A stored assignment as every read shows it: the model and the profile.

    The profile fields mirror the row's columns — ``custom`` beside its
    number, the vocabulary's default where no choice was stored.
    """

    task_key: str
    profile_id: UUID | None
    output_profile: str
    output_profile_custom: int | None


class TaskEffectiveRead(BaseModel):
    """One known task key and the tier that actually serves it.

    ``profile_id`` and ``profile_name`` are ``None`` exactly when no model
    serves — the environment tier answers. ``kind`` names the serving adapter
    either way (``fake``, ``openai-chat`` or ``anthropic``), so the page can
    say what answers without claiming the cascade's stored choice. An
    audit-only key has no serving tier: ``kind`` is ``audit``, the model
    fields are ``None``, and ``assignable`` is ``False``.

    The output profile is the honesty seam (W8): ``output_profile`` names the
    choice the serving assignment carried (``balanced`` when none did) and
    ``resolved_output_tokens`` is the number a call reserves — the target,
    ``min``-ed with the model's stored ``max_output_tokens`` where one is
    stored, the target itself where none is (an unknown ceiling is never
    invented). An audit-only key names no profile and reserves nothing:
    both fields are ``None`` there.
    """

    task_key: str
    profile_id: UUID | None
    profile_name: str | None
    kind: str
    assignable: bool
    output_profile: str | None
    resolved_output_tokens: int | None


class DriverRead(BaseModel):
    """The instance's driver kind as one word: what actually answers.

    ``fake`` while every assignable task's serving tier is the local fake
    adapter — the cascade's floor or a stored fake row; ``configured`` once
    any provider adapter serves one. The offline card claims a local driver
    only on ``fake``. The read is the tasks read's own resolution reduced to
    this word, never a second derivation, so it can never disagree with the
    task list's rows — and it fails as the tasks read fails: a provider
    whose key its tier can no longer produce is the 502 the router maps.
    """

    kind: Literal["fake", "configured"]
