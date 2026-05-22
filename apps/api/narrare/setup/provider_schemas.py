"""Setup Wizard provider-specific Pydantic schemas — Steps 4-5."""

from __future__ import annotations

from pydantic import BaseModel, Field

from narrare.setup.base_schemas import (
    AIProvider,
    StarterContent,
    StoryStructure,
    StoryTone,
)

# ---------------------------------------------------------------------------
# Step 4: AI Provider
# ---------------------------------------------------------------------------


class Step4ProviderRequest(BaseModel):
    provider: AIProvider
    api_key: str = Field(default="", max_length=200)
    model: str = Field(min_length=1, max_length=200)
    ollama_url: str = Field(default="http://localhost:11434", max_length=200)
    zai_endpoint: str = Field(default="general", max_length=50)


class ProviderModel(BaseModel):
    """A model available from a provider."""

    id: str
    name: str
    context_window: int | None = None
    supports_streaming: bool = True


class Step4ProviderResponse(BaseModel):
    valid: bool
    provider: AIProvider
    model: str
    validation_message: str = ""


class AvailableModelsResponse(BaseModel):
    provider: AIProvider
    models: list[ProviderModel]


# ---------------------------------------------------------------------------
# Step 5: Confirm + Complete
# ---------------------------------------------------------------------------


class WizardState(BaseModel):
    """Complete wizard state collected across all 5 steps."""

    # Step 1
    project_name: str
    writing_language: str
    autosave_interval: int
    # Step 2
    title: str
    author: str
    genre: str
    logline: str
    story_structure: StoryStructure
    tone: StoryTone
    # Step 3
    starter: StarterContent
    import_path: str | None
    # Step 4 (optional — skipped if skip_provider=True)
    provider: AIProvider = AIProvider.ANTHROPIC
    api_key: str = ""
    model: str = ""
    ollama_url: str = "http://localhost:11434"
    zai_endpoint: str = "general"  # "general" or "coding"
    # Provider skip flag — True when user already has providers configured
    skip_provider: bool = False


class CompleteSetupRequest(BaseModel):
    """Final request to complete setup — full wizard state."""

    state: WizardState


class CompleteSetupResponse(BaseModel):
    """Returned after successful setup completion."""

    novel_id: str
    redirect_to: str  # "/dashboard" or "/novel/{id}"
    message: str
