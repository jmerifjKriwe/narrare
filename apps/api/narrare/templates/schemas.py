"""Template API Pydantic schemas — maps domain models to HTTP responses."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TemplateInfoResponse(BaseModel):
    """Metadata summary for a single template override."""

    model_config = ConfigDict(from_attributes=True)

    entity_type: str = Field(..., description="Entity type (character, location, etc.)")
    scope: str = Field(..., description="Scope level: user, project, or global")
    scope_id: str | None = Field(default=None, description="Scope identifier UUID")
    schema_version: str = Field(default="2.0.0", description="Template schema version")
    based_on_version: str | None = Field(
        default=None, description="Bundled version this override is based on"
    )
    has_override: bool = Field(default=False, description="Whether a DB override exists")
    has_update: bool = Field(default=False, description="Whether a bundled update is available")


class TemplateDetailResponse(BaseModel):
    """Full template detail with cascade info."""

    model_config = ConfigDict(from_attributes=True)

    entity_type: str
    scope: str
    content: str
    base_content: str | None = None
    schema_version: str
    based_on_version: str | None = None
    is_overridden: bool


class SaveOverrideRequest(BaseModel):
    """Request body for saving a template override."""

    content: str = Field(
        ..., min_length=1, description="Override template content (YAML frontmatter + body)"
    )
    based_on_version: str | None = Field(
        default=None, description="Bundled version this override is based on"
    )


class UpdateInfoResponse(BaseModel):
    """Information about a template with available bundled updates."""

    model_config = ConfigDict(from_attributes=True)

    entity_type: str
    override_version: str | None = None
    current_bundled_version: str | None = None


class DiffResponse(BaseModel):
    """Side-by-side content for diff comparison."""

    model_config = ConfigDict(from_attributes=True)

    entity_type: str
    override_content: str
    bundled_content: str
