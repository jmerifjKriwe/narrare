"""
Fake setup service implementations for unit tests.

Used when SetupService tests need ProviderService or DemoLoader as dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from narrare.setup.schemas import (
    AvailableModelsResponse,
    DemoProjectInfo,
    StarterContent,
)

if TYPE_CHECKING:
    import uuid

    from narrare.setup.base_schemas import AIProvider


class FakeProviderService:
    """
    In-memory fake for ProviderServiceProtocol.

    Programmable responses for list_models and validate_connection.
    """

    def __init__(self) -> None:
        self._models_response: AvailableModelsResponse | None = None
        self._validation_result: bool = True
        self.calls: list[dict[str, Any]] = []

    def set_models_response(self, response: AvailableModelsResponse) -> None:
        """Configure the response for list_models."""
        self._models_response = response

    def set_validation_result(self, result: bool) -> None:
        """Configure the result for validate_connection."""
        self._validation_result = result

    async def list_models(
        self, provider: AIProvider, api_key: str, ollama_url: str = ""
    ) -> AvailableModelsResponse:
        self.calls.append(
            {
                "method": "list_models",
                "provider": provider,
                "api_key": api_key,
                "ollama_url": ollama_url,
            }
        )
        if self._models_response is not None:
            return self._models_response
        # Default: empty response
        return AvailableModelsResponse(provider=provider, models=[])

    async def validate_connection(
        self, provider: AIProvider, api_key: str, model: str, ollama_url: str = ""
    ) -> bool:
        self.calls.append(
            {
                "method": "validate_connection",
                "provider": provider,
                "api_key": api_key,
                "model": model,
                "ollama_url": ollama_url,
            }
        )
        return self._validation_result


class FakeDemoLoader:
    """
    In-memory fake for DemoLoaderProtocol.

    Programmable responses for get_info and load.
    """

    def __init__(self) -> None:
        self._info: DemoProjectInfo | None = None
        self.calls: list[dict[str, Any]] = []

    def set_info(self, info: DemoProjectInfo) -> None:
        """Configure the response for get_info."""
        self._info = info

    def get_info(self, starter: StarterContent) -> DemoProjectInfo:
        """Synchronous get_info — mirrors real DemoLoader."""
        self.calls.append({"method": "get_info", "starter": starter})
        if self._info is not None:
            return self._info
        # Default info
        return DemoProjectInfo(
            id=starter,
            title="Fake Demo",
            language="en",
            genre="Test",
            chapter_count=1,
            character_count=0,
            word_count=100,
            description="Fake demo for testing",
        )

    async def load(
        self, starter: StarterContent, novel_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        """Load demo content — no-op in fake."""
        self.calls.append({"method": "load", "starter": starter, "novel_id": novel_id})
