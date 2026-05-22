"""Setup Wizard step validation functions.

Pure validation logic for each wizard step, extracted from SetupService
for RULE-04 compliance (file size limits).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from narrare.setup.schemas import (
    AIProvider,
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
)
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from narrare.setup.contracts import DemoLoaderProtocol, ProviderServiceProtocol

_SUPPORTED_LANGUAGES = {"en", "de", "fr"}


async def validate_step1(request: Step1LocationRequest) -> Step1LocationResponse:
    """Validate Step 1 (Location) inputs.

    Args:
        request: Step 1 form data.

    Returns:
        Step1LocationResponse with valid=True if all checks pass.

    Raises:
        ValidationError: If validation fails.
    """
    if request.writing_language not in _SUPPORTED_LANGUAGES:
        raise ValidationError(
            f"Language '{request.writing_language}' not supported. "
            f"Supported: {sorted(_SUPPORTED_LANGUAGES)}"
        )

    return Step1LocationResponse(
        valid=True,
        project_name=request.project_name,
        writing_language=request.writing_language,
        autosave_interval=request.autosave_interval,
    )


async def validate_step2(request: Step2NovelRequest) -> Step2NovelResponse:
    """Validate Step 2 (Novel) inputs.

    Args:
        request: Step 2 form data.

    Returns:
        Step2NovelResponse with valid=True.
    """
    return Step2NovelResponse(valid=True, title=request.title)


async def validate_step3(
    request: Step3StarterRequest,
    demo_loader: DemoLoaderProtocol,
) -> Step3StarterResponse:
    """Validate Step 3 (Starter content) inputs.

    Args:
        request: Step 3 form data.
        demo_loader: Demo content loader.

    Returns:
        Step3StarterResponse with demo info if applicable.

    Raises:
        ValidationError: If import path is missing or doesn't exist.
    """
    if request.starter == StarterContent.IMPORT:
        if not request.import_path:
            raise ValidationError("Import path is required when starter is 'import'")
        import_dir = Path(request.import_path)
        if not import_dir.exists() or not import_dir.is_dir():
            raise ValidationError(f"Import directory does not exist: {request.import_path}")
        return Step3StarterResponse(valid=True, starter=request.starter)

    demo_info: DemoProjectInfo | None = None
    if request.starter in (
        StarterContent.DEMO_FANTASY,
        StarterContent.DEMO_SCIFI,
        StarterContent.DEMO_GERMAN,
    ):
        demo_info = demo_loader.get_info(request.starter)

    return Step3StarterResponse(
        valid=True,
        starter=request.starter,
        demo_info=demo_info,
    )


async def validate_step4(
    request: Step4ProviderRequest,
    provider_service: ProviderServiceProtocol,
) -> Step4ProviderResponse:
    """Validate Step 4 (AI Provider) by making a real minimal API call.

    Args:
        request: Provider, API key, and model selection.
        provider_service: Provider connection validator.

    Returns:
        Step4ProviderResponse with valid=True if connection succeeds.

    Raises:
        ValidationError: If connection validation fails.
    """
    if request.provider != AIProvider.OLLAMA and not request.api_key:
        raise ValidationError("API key is required for this provider")

    error = await provider_service.validate_connection(
        provider=request.provider,
        api_key=request.api_key,
        model=request.model,
        ollama_url=request.ollama_url,
        zai_endpoint=request.zai_endpoint,
    )

    if error:
        raise ValidationError(error)

    return Step4ProviderResponse(
        valid=True,
        provider=request.provider,
        model=request.model,
        validation_message="Connection verified successfully",
    )
