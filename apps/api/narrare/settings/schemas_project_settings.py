"""Project-settings schemas (STATS-001 E5) — per-novel settings models.

RULE-04 split from ``schemas.py`` (same convention as
``schemas_providers.py`` / ``schemas_tones.py``): the project-settings
GET/PATCH models plus the v1 writing-goal payload they carry. The names
are re-exported from ``narrare.settings.schemas`` so existing import
paths stay stable.
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class WritingGoalsPayload(BaseModel):
    """Novel writing-goal shape, v1 (STATS-001 spec E-4, ADR-095).

    The stored ``project_settings.writing_goals`` JSONB holds exactly this
    object — v1 ships one key with room to grow. ``extra="forbid"`` keeps
    the whole-object-replace PATCH strict: unknown keys ⇒ 422, so a typo
    can never silently no-op. ``target_words`` must be an int ≥ 0 or null
    (garbage ⇒ 422 via pydantic → FastAPI RequestValidationError); the
    analytics service additionally treats ≤ 0 as "no goal" (policy, not
    shape — see ``settings.writing_goals.parse_target_words``).
    """

    model_config = ConfigDict(extra="forbid")

    target_words: int | None = Field(
        default=None,
        ge=0,
        description="Novel word-count target (null = no target set)",
    )


class ProjectSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    novel_id: uuid.UUID
    autosave_interval: int
    default_language: str
    ai_provider: str
    ai_model: str
    model_overrides: str
    category_overrides: dict[str, object]
    intent_overrides: dict[str, object]
    token_limit_overrides: dict[str, object]
    # Spec 3: per-novel opt-out flag for the series-voice Delta model (ADR-078).
    # Read from the ORM column added in migration 0039 (defaults True).
    use_series_voice: bool = True
    # STATS-001 (spec E-4/E-5): the stored v1 goal object; null = no goal.
    # RESPONSE side is a deliberate LOOSE passthrough (fix round 1): JSONB
    # is schemaless, so a corrupt stored row must degrade, never fail the
    # read. Typed ``object`` on purpose — even ``dict[str, object] | None``
    # would let pydantic reject top-level non-dict corruption (50000, "x",
    # [1], true) and 500 the GET/PATCH; analytics degrades identically via
    # ``settings.writing_goals.parse_target_words``. Strict v1 validation
    # lives on the REQUEST side (``WritingGoalsPayload`` on the PATCH
    # request below).
    writing_goals: object | None = None
    updated_at: datetime


class UpdateProjectSettingsRequest(BaseModel):
    autosave_interval: int | None = Field(default=None, ge=0, le=3600)
    default_language: str | None = Field(default=None, min_length=2, max_length=10)
    ai_provider: str | None = Field(default=None, max_length=50)
    ai_model: str | None = Field(default=None, max_length=200)
    model_overrides: str | None = None  # JSON string
    # Spec 3: per-novel opt-out. ``False`` opts out of the series-voice Delta
    # model (the novel falls back to its own author_voice only). ``None`` =
    # "not provided" → omitted from the PATCH (repository uses exclude_none).
    use_series_voice: bool | None = Field(default=None)
    # STATS-001 (spec E-4/E-5): whole-object replace semantics v1 — a
    # provided object REPLACES the stored goal wholesale (v1 has exactly one
    # key); ``{"target_words": null}`` is the explicit unset. Omitted =
    # untouched (``exclude_none`` drops it — same PATCH contract as the
    # sibling fields).
    writing_goals: WritingGoalsPayload | None = Field(default=None)

    @field_serializer("writing_goals")
    def _serialize_writing_goals(
        self, goals: WritingGoalsPayload | None
    ) -> dict[str, object] | None:
        """Emit a plain dict so the repository setattr-loop stores JSON.

        ``model_dump`` applies this serializer, so the repository's existing
        ``model_dump(exclude_none=True)`` → ``setattr`` contract keeps working
        unchanged — a bare pydantic object would break JSONB serialization.
        """
        return None if goals is None else goals.model_dump()
