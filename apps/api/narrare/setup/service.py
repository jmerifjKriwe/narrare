"""
Setup Wizard Service — validates each step and completes setup.

Each step delegates validation to ``_validation.py`` (RULE-04 split).
The ``complete()`` method creates all DB records atomically.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare.novels.models import Novel
from narrare.settings.models import ProjectSettings
from narrare.setup._validation import validate_step1, validate_step2, validate_step3, validate_step4
from narrare.setup.schemas import (
    AIProvider,
    CompleteSetupResponse,
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

    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.settings.repository import ProjectSettingsRepository, UserSettingsRepository
    from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
    from narrare.settings.user_providers_repository import UserProvidersRepository
    from narrare.setup.contracts import DemoLoaderProtocol, ProviderServiceProtocol

logger = structlog.get_logger(__name__)


class SetupService:
    """Orchestrates the 5-step setup wizard."""

    def __init__(
        self,
        session: AsyncSession,
        novel_repo: NovelRepositoryProtocol,
        user_settings_repo: UserSettingsRepository,
        project_settings_repo: ProjectSettingsRepository,
        provider_service: ProviderServiceProtocol,
        demo_loader: DemoLoaderProtocol,
        providers_repo: UserProvidersRepository,
        ai_settings_repo: UserAiSettingsRepository,
    ) -> None:
        self._session = session
        self._novel_repo = novel_repo
        self._user_settings_repo = user_settings_repo
        self._project_settings_repo = project_settings_repo
        self._provider_service = provider_service
        self._demo_loader = demo_loader
        self._providers_repo = providers_repo
        self._ai_settings_repo = ai_settings_repo

    # --- Step validation (delegates to _validation.py) ---------------------

    async def validate_step1(self, request: Step1LocationRequest) -> Step1LocationResponse:
        return await validate_step1(request)

    async def validate_step2(self, request: Step2NovelRequest) -> Step2NovelResponse:
        return await validate_step2(request)

    async def validate_step3(self, request: Step3StarterRequest) -> Step3StarterResponse:
        return await validate_step3(request, self._demo_loader)

    async def validate_step4(self, request: Step4ProviderRequest) -> Step4ProviderResponse:
        return await validate_step4(request, self._provider_service)

    # --- Complete: create all DB records -----------------------------------

    async def complete(self, user_id: str, state: WizardState) -> CompleteSetupResponse:
        """
        Create all records from the completed wizard state.

        Creates: Novel, ProjectSettings, UserProvider, UserAiSettings,
        UserSettings update. If demo starter: loads demo chapters and KB stubs.

        All in a single transaction — rollback on any failure.
        """
        uid = uuid.UUID(user_id)

        # Create novel
        novel = Novel(
            user_id=uid,
            title=state.title,
            author=state.author,
            genre=state.genre,
            writing_language=state.writing_language,
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

        # Create provider records — ONLY if Step 4 was not skipped
        if not state.skip_provider:
            from narrare_core.crypto import encrypt

            encrypted_key = encrypt(state.api_key) if state.provider != AIProvider.OLLAMA else ""

            base_url: str | None = None
            if state.provider == AIProvider.ZAI and state.zai_endpoint == "coding":
                base_url = "https://api.z.ai/api/coding/paas/v4"

            provider_entry = await self._providers_repo.create(
                user_id=uid,
                provider_name=state.provider.value,
                api_key_encrypted=encrypted_key,
                base_url=base_url,
            )

            # Set default model in user_ai_settings
            await self._ai_settings_repo.update(
                uid,
                default_provider_id=provider_entry.id,
                default_model=state.model,
            )

            ai_provider_name = state.provider.value
            ai_model = state.model
        else:
            # Skipping provider — look up user's existing default provider
            logger.info("setup_skip_provider", user_id=user_id, reason="existing_providers")
            existing_settings = await self._ai_settings_repo.get(uid)
            ai_provider_name = ""
            ai_model = ""
            if existing_settings and existing_settings.default_provider_id:
                from sqlalchemy import select

                from narrare.settings.models import UserProvider

                result = await self._session.execute(
                    select(UserProvider).where(
                        UserProvider.id == existing_settings.default_provider_id
                    )
                )
                existing_provider = result.scalar_one_or_none()
                if existing_provider:
                    ai_provider_name = existing_provider.provider_name
                    ai_model = existing_settings.default_model or ""

        # Create project settings (legacy)
        project_settings = ProjectSettings(
            novel_id=novel.id,
            autosave_interval=state.autosave_interval,
            default_language=state.writing_language,
            ai_provider=ai_provider_name,
            ai_model=ai_model,
        )
        self._session.add(project_settings)

        # NOTE: Do NOT set ui_language from writing_language — they are
        # orthogonal. UI language is managed by next-intl based on browser
        # locale. Writing language is the novel's creative language.
        # (Previously this incorrectly set ui_language=state.language)

        # Load demo content if selected
        if state.starter in (
            StarterContent.DEMO_FANTASY,
            StarterContent.DEMO_SCIFI,
            StarterContent.DEMO_GERMAN,
        ):
            try:
                await self._demo_loader.load(state.starter, novel.id, uid)
                redirect_to = f"/novel/{novel.id}"
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
