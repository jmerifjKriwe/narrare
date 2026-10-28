"""The provider-profile tables and the llm_calls audit: what a user configures
and the evidence later work asserts on (plan §3.4, WP2a design §Goals).

The tables are kernel machinery, not shared domain vocabulary, so they live
next to the provider boundary rather than in contracts. A user's
``ProviderProfile`` rows carry their own provider choice — ``api_key`` holds
Fernet ciphertext or stays empty when the OS keychain holds the plaintext
(:mod:`app.kernel.secrets` decides; never plaintext) — and a
``TaskAssignment`` points one task key at one profile. ``LlmCall`` is a log,
not user data: ``novel_id`` and ``profile_id`` carry no foreign key on
purpose, so the audit outlives the novel and the profile it names.
``cost_usd`` stays NULL until a catalog prices it — NULL, never 0 — and
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

PROFILE_KINDS = ("fake", "openai-chat")
"""The kinds of profile a user can save. A short closed vocabulary in code
beside a free-text column, like ``ENTITY_TYPES`` — validating a kind is the
settings service's gate (WP2a T4), not the database's."""


class ProviderProfile(UserOwned):
    """One user's saved provider configuration: what to call and how to tune it.

    ``is_default`` carries exactly-one-per-user semantics: the settings
    service keeps the flip in one transaction (design D7), and a partial
    unique index makes the database the last word on it — two concurrent
    creates cannot both mint a default. ``api_key_hint`` holds the last four
    characters for masked reads without a keychain round-trip — a hint, not
    a secret.
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
    # A PROFILE_KINDS value; free text to the database.
    kind: Mapped[str] = mapped_column(String(40))
    base_url: Mapped[str | None] = mapped_column(String(500))
    model: Mapped[str | None] = mapped_column(String(200))
    # Exactly what secrets.save_key returned: "" (keyring tier) or ciphertext.
    api_key: Mapped[str] = mapped_column(Text, default="")
    api_key_hint: Mapped[str | None] = mapped_column(String(8))
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
    prompt_text: Mapped[str] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
