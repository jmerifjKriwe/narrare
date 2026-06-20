"""Setup Wizard module — re-exports all schemas."""

from .base_schemas import (
    AIProvider,
    DemoListResponse,
    DemoProjectInfo,
    StarterContent,
    Step1LocationRequest,
    Step1LocationResponse,
    Step2NovelRequest,
    Step2NovelResponse,
    Step3StarterRequest,
    Step3StarterResponse,
    StoryStructure,
    StoryTone,
)
from .provider_schemas import (
    AvailableModelsResponse,
    CompleteSetupRequest,
    CompleteSetupResponse,
    ModelCatalogProvenance,
    ProviderModel,
    Step4ProviderRequest,
    Step4ProviderResponse,
    WizardState,
)

__all__ = [
    "AIProvider",
    "AvailableModelsResponse",
    "CompleteSetupRequest",
    "CompleteSetupResponse",
    "DemoListResponse",
    "DemoProjectInfo",
    "ModelCatalogProvenance",
    "ProviderModel",
    "StarterContent",
    "Step1LocationRequest",
    "Step1LocationResponse",
    "Step2NovelRequest",
    "Step2NovelResponse",
    "Step3StarterRequest",
    "Step3StarterResponse",
    "Step4ProviderRequest",
    "Step4ProviderResponse",
    "StoryStructure",
    "StoryTone",
    "WizardState",
]
