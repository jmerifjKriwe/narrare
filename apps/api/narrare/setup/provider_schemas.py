"""Setup Wizard provider-specific Pydantic schemas — Steps 4-5."""

from __future__ import annotations

from datetime import date  # noqa: TC003

from pydantic import BaseModel, Field

from narrare.setup.base_schemas import (
    AIProvider,
    StarterContent,
    StoryStructure,
    StoryTone,
)
from narrare.setup.constants import OLLAMA_DEFAULT_URL

# ---------------------------------------------------------------------------
# Step 4: AI Provider
# ---------------------------------------------------------------------------


class Step4ProviderRequest(BaseModel):
    provider: AIProvider
    api_key: str = Field(default="", max_length=200)
    model: str = Field(min_length=1, max_length=200)
    ollama_url: str = Field(default=OLLAMA_DEFAULT_URL, max_length=200)
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


class ModelCatalogProvenance(BaseModel):
    """Provenance metadata for a model catalog response — CR-AUFG-08-06.

    Tells clients whether the models in an ``AvailableModelsResponse``
    came from a live provider API (``source="live"``) or from the
    bundled static fallback list (``source="bundled-fallback"``).

    When ``source`` is ``"bundled-fallback"``, ``last_reviewed`` carries
    the date the fallback list was last refreshed, so the UI can render
    a "stale/offline fallback" label. When ``source`` is ``"live"``,
    ``last_reviewed`` is ``None`` (the data is real-time, not cached).

    Constants for ``source`` values live in ``setup/constants.py``:
    ``LIVE_CATALOG_SOURCE``, ``FALLBACK_CATALOG_SOURCE``,
    ``FALLBACK_CATALOG_LAST_REVIEWED``.
    """

    source: str = Field(
        description="Where the model list came from: 'live' or 'bundled-fallback'.",
    )
    last_reviewed: date | None = Field(
        default=None,
        description=(
            "When the fallback catalog was last reviewed (only set for "
            "'bundled-fallback'). None for live-fetched models."
        ),
    )


class AvailableModelsResponse(BaseModel):
    provider: AIProvider
    models: list[ProviderModel]
    provenance: ModelCatalogProvenance | None = None


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
    ollama_url: str = OLLAMA_DEFAULT_URL
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
