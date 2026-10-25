"""The llm_calls table: one row per provider call, the evidence later work
asserts on (plan §3.4).

The table is kernel machinery, not shared domain vocabulary, so it lives next
to the provider boundary rather than in contracts. Nothing user-facing reads
it; :func:`app.kernel.llm.audit.record_call` is the one writer. A row is a
log, not user data: ``novel_id`` carries no foreign key on purpose, so the
audit outlives the novel it names. ``cost_usd`` stays NULL until a catalog
prices it — NULL, never 0 — and no ``profile_id`` exists until a profile
table does (WP2).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.db.base import UserOwned

# The audit's whole status vocabulary: a call answered, or one that errored —
# a failed job writes no row at all (D3/D14), but a failed stream does.
OK = "ok"
ERROR = "error"


class LlmCall(UserOwned):
    """One provider call: what was asked, what came back, what it cost to wait."""

    __tablename__ = "llm_calls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # No FK on purpose: a log row outlives its novel (plan §3.4).
    novel_id: Mapped[UUID | None] = mapped_column(Uuid)
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
