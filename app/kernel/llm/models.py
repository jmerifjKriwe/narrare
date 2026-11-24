"""The provider tables and the llm_calls audit: what a user configures
and the evidence later work asserts on (plan §3.4, WP2a design §Goals).

The tables are kernel machinery, not shared domain vocabulary, so they live
next to the provider boundary rather than in contracts. A user's
``LLMProvider`` row is the saved endpoint — the vendor, the base URL, the
key — and a ``ProviderProfile`` (a saved model) points at exactly one of
them and carries the model choice and tuning. A ``TaskAssignment``
points one task key at one profile. ``LlmCall`` is a log, not user data:
``novel_id`` and ``profile_id`` carry no foreign key on purpose, so the
audit outlives the novel and the profile it names. ``cost_usd`` stays NULL
until a catalog prices it — NULL, never 0 — and
:func:`app.kernel.llm.audit.record_call` is the one writer.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import UserOwned

# The audit's whole status vocabulary: a call answered, or one that errored —
# a failed job writes no row at all (D3/D14), but a failed stream does.
OK = "ok"
ERROR = "error"

PROVIDER_KINDS = ("fake", "openai-chat", "anthropic")
"""The kinds of provider a user can save, beside the free-text ``kind``
column — validating one is the settings service's gate, not the database's.
The list is open at one end on purpose: a provider kind arrives that no code
but its adapter and the catalog knows, and this list is where it lands."""

OUTPUT_PROFILES: dict[str, int] = {
    "quick": 1_024,
    "balanced": 4_096,
    "long_texts": 12_288,
    "comprehensive": 32_768,
}
"""The named output profiles and their targets, in output tokens (W8 ruling 5).

These are realistic numbers against the models the catalog actually carries
(200 k to 1 M-token windows), not conservative relics — the point of the ruling.
A profile binds per task, not per model: the same model serves a short
continuation and a long extraction, and the assignment row stores which one
applies. The targets are what a call aims for, not ceilings — resolution
caps at the model's stored ``max_output_tokens`` when one exists
(:func:`app.kernel.llm.resolution`), and the catalog's knowledge never caps
them. Validating a name is the settings schema's gate, like PROVIDER_KINDS.
"""

DEFAULT_OUTPUT_PROFILE = "balanced"
"""The profile an assignment without a stored choice carries.

The profile column has no two-state semantics (W8): absent and carried null
both mean this, the column defaults to it, and the migration backfills it —
a save that does not name a profile states ``balanced`` by that fact.
"""

CUSTOM_OUTPUT_PROFILE = "custom"
"""The fifth name: not in :data:`OUTPUT_PROFILES` because it is its number.

An assignment with this name stores the explicit token target in
``output_profile_custom``; the API carries that number in place of a name.
"""

OUTPUT_PROFILE_CUSTOM_MAX = 2_147_483_647
"""The Integer column's own ceiling for a custom target.

A number beyond it would overflow at the write; the schema's gate refuses it
with the field instead — the same shape as the word goal's bound. A custom
number under a stored model ceiling is bounded by the save gate, not here.
"""


class LLMProvider(UserOwned):
    """One user's saved provider: the endpoint its models hang off.

    The row exists so a model names a provider instead of repeating it:
    ``vendor`` and ``models_url`` are facts about the endpoint, ``api_key``
    the two-tier storage — what :func:`app.kernel.secrets.save_key`
    returned, or ``""`` when the OS keychain keeps the plaintext.
    ``base_url`` is nullable for a kind with no endpoint of its own, exactly
    the fake's shape today.
    """

    __tablename__ = "llm_providers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    # A PROVIDER_KINDS value; free text to the database.
    kind: Mapped[str] = mapped_column(String(40))
    base_url: Mapped[str | None] = mapped_column(String(500))
    # Where the endpoint lists its models, when it has such a URL at all.
    models_url: Mapped[str | None] = mapped_column(String(500))
    # The vendor's own naming, for the catalog to key on — free text.
    vendor: Mapped[str | None] = mapped_column(String(40))
    # Exactly what secrets.save_key returned: "" (keyring tier) or ciphertext.
    api_key: Mapped[str] = mapped_column(Text, default="")
    api_key_hint: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ProviderProfile(UserOwned):
    """One user's saved model: which provider serves it and how to tune it.

    Everything endpoint-shaped lives on the provider this row names; what is
    left here is the identity (name, model string) and the tuning, plus the
    provider pointer the write gate refuses to leave unset or point across
    users. ``is_default`` carries exactly-one-per-user semantics: the
    settings service keeps the flip in one transaction (design D7), and a
    partial unique index makes the database the last word on it — two
    concurrent creates cannot both mint a default.
    """

    __tablename__ = "provider_profiles"
    __table_args__ = (
        # One default per user, decided by the database: two creates that
        # both saw an empty table both raise themselves, and exactly one
        # insert commits (F-11).
        Index(
            "uq_provider_profiles_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    # The provider row this profile points at — its endpoint and key. NOT
    # NULL since the revision that dropped the duplicated columns: a model
    # without a provider is not a configuration. The FK is RESTRICT: the
    # delete guard answers first with the named 409, and the database is
    # the atomic backstop behind it — a pointer that slipped past the guard
    # refuses the delete, it never cascades away.
    provider_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("llm_providers.id", ondelete="RESTRICT")
    )
    model: Mapped[str | None] = mapped_column(String(200))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    context_window: Mapped[int | None] = mapped_column(Integer)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    temperature: Mapped[float | None] = mapped_column(Float)
    request_timeout: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class TaskAssignment(UserOwned):
    """One user's choice of profile for one task key (``chat.ask`` and friends).

    ``unique (user_id, task_key)``: one choice per task. A deleted profile
    cascades its assignments at the database, and the affected tasks fall
    back down the resolution cascade — the resolver's story (WP2a T3), not
    the table's.

    The row also carries the task's output profile (W8): ``output_profile``
    names an :data:`OUTPUT_PROFILES` entry or :data:`CUSTOM_OUTPUT_PROFILE`,
    never NULL and defaulted to :data:`DEFAULT_OUTPUT_PROFILE` — absent and
    carried null both mean it, so no two-state semantics live here. A custom
    choice stores its explicit number in ``output_profile_custom``; the save
    gate bounds that number to the assigned model's stored
    ``max_output_tokens`` when one exists.
    """

    __tablename__ = "task_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "task_key", name="uq_task_assignments_user_task"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_key: Mapped[str] = mapped_column(String(100))
    profile_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("provider_profiles.id", ondelete="CASCADE")
    )
    # A vocabulary name, free text to the database — the gate is the schema's.
    output_profile: Mapped[str] = mapped_column(
        String(20), default=DEFAULT_OUTPUT_PROFILE, server_default=DEFAULT_OUTPUT_PROFILE
    )
    # The explicit target when output_profile is "custom"; NULL otherwise.
    output_profile_custom: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class LlmCall(UserOwned):
    """One provider call: what was asked, what came back, what it cost to wait."""

    __tablename__ = "llm_calls"
    # The newest-row read behind the settings page's failure mark asks
    # exactly this slice: user, model, newest first — the index is its
    # shape, so the audit's growth never turns the mark into a scan. The
    # composite opens with user_id, so the base's single-column index would
    # answer no read it does not — its write doubles for nothing (issue
    # #749), which is why this table carries no ix_llm_calls_user_id.
    __table_args__ = (
        Index("ix_llm_calls_user_id_profile_id_created_at", "user_id", "profile_id", "created_at"),
    )

    # Overrides ``UserOwned.user_id`` to drop the inherited ``index=True``:
    # the composite above already leads with user_id, so the single-column
    # index is pure write overhead on every call row.
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # No FK on purpose: a log row outlives its novel (plan §3.4).
    novel_id: Mapped[UUID | None] = mapped_column(Uuid)
    # No FK on purpose either: a log row outlives its profile the same way.
    profile_id: Mapped[UUID | None] = mapped_column(Uuid)
    # What the capability named for this call: "knowledge.extract-entities"
    # and friends.
    task_key: Mapped[str] = mapped_column(String(100))
    # NULL until WP4 keys prompts for reuse.
    prompt_key: Mapped[str | None] = mapped_column(String(100))
    provider_kind: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(200))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    # NULL until WP2's catalog — never 0: an unknown price is not a free call.
    cost_usd: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text)
    # The wire code the failure maps to (contract.error_code), NULL for a
    # clean call and for a stream the consumer walked away from — the row
    # names the kind of refusal, the sentence the surfaces showed is the
    # web's business.
    error_code: Mapped[str | None] = mapped_column(String(40))
    prompt_text: Mapped[str] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
