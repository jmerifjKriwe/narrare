"""Setup Wizard Pydantic schemas — all 5 steps.

This module re-exports all schemas from base_schemas and provider_schemas
for backward compatibility. New code should import from the specific modules.
"""

# Re-export everything from base_schemas
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

# Re-export everything from provider_schemas
from .provider_schemas import (
    AvailableModelsResponse,
    CompleteSetupRequest,
    CompleteSetupResponse,
    ProviderModel,
    Step4ProviderRequest,
    Step4ProviderResponse,
    WizardState,
)

__all__ = [  # noqa: RUF022 (grouped by step for clarity)
    # Enums
    "AIProvider",
    "StarterContent",
    "StoryStructure",
    "StoryTone",
    # Step 1
    "Step1LocationRequest",
    "Step1LocationResponse",
    # Step 2
    "Step2NovelRequest",
    "Step2NovelResponse",
    # Step 3
    "Step3StarterRequest",
    "Step3StarterResponse",
    "DemoProjectInfo",
    "DemoListResponse",
    # Step 4
    "Step4ProviderRequest",
    "Step4ProviderResponse",
    "ProviderModel",
    "AvailableModelsResponse",
    # Step 5
    "CompleteSetupRequest",
    "CompleteSetupResponse",
    "WizardState",
]
