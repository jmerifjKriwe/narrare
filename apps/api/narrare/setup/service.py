"""
Setup Wizard Service — validates each step and completes setup.

Each step has its own validate_* method that returns a typed response.
The complete() method creates all DB records atomically.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import HTTPException, status

from narrare.novels.models import Novel
from narrare.novels.repository import NovelRepository
from narrare.settings.models import ProjectSettings
from narrare.settings.repository import ProjectSettingsRepository, UserSettingsRepository
from narrare.setup.demo_loader import DemoLoader
from narrare.setup.provider_service import ProviderService
from narrare.setup.schemas import (
    AIProvider,
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

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_SUPPORTED_LANGUAGES = {"en", "de", "fr"}


class SetupService:
    """Orchestrates the 5-step setup wizard."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._novel_repo = NovelRepository(session)
        self._user_settings_repo = UserSettingsRepository(session)
        self._project_settings_repo = ProjectSettingsRepository(session)
        self._provider_service = ProviderService()
        self._demo_loader = DemoLoader(session)

    # -----------------------------------------------------------------------
    # Step 1: Location
    # -----------------------------------------------------------------------

    async def validate_step1(self, request: Step1LocationRequest) -> Step1LocationResponse:
        """
        Validate Step 1 (Location) inputs.

        Checks project name validity and supported language.

        Args:
            request: Step 1 form data.

        Returns:
            Step1LocationResponse with valid=True if all checks pass.

        Raises:
            HTTPException 422: If validation fails with a user-facing message.
        """
        if request.language not in _SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Language '{request.language}' not supported. "
                f"Supported: {sorted(_SUPPORTED_LANGUAGES)}",
            )

        return Step1LocationResponse(
            valid=True,
            project_name=request.project_name,
            language=request.language,
            autosave_interval=request.autosave_interval,
        )

    # -----------------------------------------------------------------------
    # Step 2: Novel
    # -----------------------------------------------------------------------

    async def validate_step2(self, request: Step2NovelRequest) -> Step2NovelResponse:
        """
        Validate Step 2 (Novel) inputs.

        Title is the only required field; everything else is optional.

        Args:
            request: Step 2 form data.

        Returns:
            Step2NovelResponse with valid=True.
        """
        return Step2NovelResponse(valid=True, title=request.title)

    # -----------------------------------------------------------------------
    # Step 3: Starter content
    # -----------------------------------------------------------------------

    async def validate_step3(self, request: Step3StarterRequest) -> Step3StarterResponse:
        """
        Validate Step 3 (Starter content) inputs.

        For IMPORT starter: validates the import path exists.
        For demo starters: returns demo metadata.

        Args:
            request: Step 3 form data.

        Returns:
            Step3StarterResponse with demo info if applicable.

        Raises:
            HTTPException 422: If import path is missing or doesn't exist.
        """
        if request.starter == StarterContent.IMPORT:
            if not request.import_path:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Import path is required when starter is 'import'",
                )
            import_dir = Path(request.import_path)
            if not import_dir.exists() or not import_dir.is_dir():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Import directory does not exist: {request.import_path}",
                )
            return Step3StarterResponse(valid=True, starter=request.starter)

        demo_info: DemoProjectInfo | None = None
        if request.starter in (
            StarterContent.DEMO_FANTASY,
            StarterContent.DEMO_SCIFI,
            StarterContent.DEMO_GERMAN,
        ):
            demo_info = self._demo_loader.get_info(request.starter)

        return Step3StarterResponse(
            valid=True,
            starter=request.starter,
            demo_info=demo_info,
        )

    # -----------------------------------------------------------------------
    # Step 4: AI Provider
    # -----------------------------------------------------------------------

    async def validate_step4(self, request: Step4ProviderRequest) -> Step4ProviderResponse:
        """
        Validate Step 4 (AI Provider) by making a real minimal API call.

        Args:
            request: Provider, API key, and model selection.

        Returns:
            Step4ProviderResponse with valid=True if connection succeeds.

        Raises:
            HTTPException 422: If connection validation fails.
        """
        if request.provider != AIProvider.OLLAMA and not request.api_key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="API key is required for this provider",
            )

        valid = await self._provider_service.validate_connection(
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            ollama_url=request.ollama_url,
        )

        if not valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Could not connect to the AI provider. "
                    "Please check your API key and selected model."
                ),
            )

        return Step4ProviderResponse(
            valid=True,
            provider=request.provider,
            model=request.model,
            validation_message="Connection verified successfully",
        )

    # -----------------------------------------------------------------------
    # Complete: create all DB records
    # -----------------------------------------------------------------------

    async def complete(self, user_id: str, state: WizardState) -> CompleteSetupResponse:
        """
        Create all records from the completed wizard state.

        Creates: Novel, ProjectSettings, UserSettings update.
        If demo starter: loads demo chapters and KB stubs.

        All in a single transaction — rollback on any failure.

        Args:
            user_id: The authenticated user's ID.
            state: Complete wizard state from all 5 steps.

        Returns:
            CompleteSetupResponse with novel_id and redirect URL.
        """
        uid = uuid.UUID(user_id)

        # Create novel
        novel = Novel(
            user_id=uid,
            title=state.title,
            author=state.author,
            genre=state.genre,
            language=state.language,
            tone=state.tone.value,
            story_structure=state.story_structure.value,
            logline=state.logline,
            is_demo=state.starter
            in (
                StarterContent.DEMO_FANTASY,
                StarterContent.DEMO_SCIFI,
                StarterContent.DEMO_GERMAN,
            ),
        )
        self._session.add(novel)
        await self._session.flush()

        logger.info("setup_novel_created", novel_id=str(novel.id), user_id=user_id)

        # Create project settings
        project_settings = ProjectSettings(
            novel_id=novel.id,
            autosave_interval=state.autosave_interval,
            default_language=state.language,
            ai_provider=state.provider.value,
            ai_model=state.model,
        )
        self._session.add(project_settings)

        # Update user settings with preferred language
        from narrare.settings.schemas import UpdateUserSettingsRequest

        await self._user_settings_repo.update(
            uid,
            UpdateUserSettingsRequest(ui_language=state.language),
        )

        # Load demo content if selected
        if state.starter in (
            StarterContent.DEMO_FANTASY,
            StarterContent.DEMO_SCIFI,
            StarterContent.DEMO_GERMAN,
        ):
            try:
                await self._demo_loader.load(state.starter, novel.id, uid)
                redirect_to = f"/novel/{novel.id}/editor"
            except FileNotFoundError:
                logger.warning(
                    "demo_content_missing",
                    starter=state.starter.value,
                    message="Demo files not found — starting with blank novel",
                )
                redirect_to = "/dashboard"
        else:
            redirect_to = "/dashboard"

        await self._session.flush()

        logger.info(
            "setup_complete",
            novel_id=str(novel.id),
            starter=state.starter.value,
            redirect=redirect_to,
        )

        return CompleteSetupResponse(
            novel_id=str(novel.id),
            redirect_to=redirect_to,
            message="Setup complete! Your writing environment is ready.",
        )
