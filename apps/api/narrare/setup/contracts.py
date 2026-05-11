"""Setup service contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.setup.schemas import (
        AIProvider,
        AvailableModelsResponse,
        CompleteSetupResponse,
        DemoProjectInfo,
        StarterContent,
        Step1LocationRequest,
        Step1LocationResponse,
        Step2NovelRequest,
        Step2NovelResponse,
        Step3StarterRequest,
        Step3StarterResponse,
        Step4ProviderRequest,
        Step4ProviderResponse,
        WizardState,
    )


@runtime_checkable
class SetupServiceProtocol(Protocol):
    async def validate_step1(self, request: Step1LocationRequest) -> Step1LocationResponse: ...
    async def validate_step2(self, request: Step2NovelRequest) -> Step2NovelResponse: ...
    async def validate_step3(self, request: Step3StarterRequest) -> Step3StarterResponse: ...
    async def validate_step4(self, request: Step4ProviderRequest) -> Step4ProviderResponse: ...
    async def complete(self, user_id: str, state: WizardState) -> CompleteSetupResponse: ...


@runtime_checkable
class ProviderServiceProtocol(Protocol):
    async def list_models(
        self, provider: AIProvider, api_key: str, ollama_url: str
    ) -> AvailableModelsResponse: ...
    async def validate_connection(
        self, provider: AIProvider, api_key: str, model: str, ollama_url: str
    ) -> bool: ...


@runtime_checkable
class DemoLoaderProtocol(Protocol):
    def get_info(self, starter: StarterContent) -> DemoProjectInfo: ...
    async def load(
        self, starter: StarterContent, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> None: ...
