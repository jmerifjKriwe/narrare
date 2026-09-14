"""Invocation-pipeline composition tests for NameGeneratorService (ADR-048 Mode 2).

Verifies that ``generate_names`` calls ``compose_name_invocation`` with the
correct arguments (project_id, language, prompt_context) and that the enriched
context is passed to the PromptComposer.  Also verifies backward-compatible
behaviour when no pipeline is wired.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from narrare.generation.name_service import NameGeneratorService
from narrare.generation.schemas import GenderEnum, NameType
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from narrare_core.llm import ResolvedModelConfig
    from tests.fakes.fake_llm_gateway import FakeModelRegistry

from ._ownership_fakes import permissive_novel_repo
from .conftest import SAMPLE_ARRAY_RESPONSE, _default_request, _static_resolution

# ---------------------------------------------------------------------------
# Invocation composition — verifies compose_name_invocation (ADR-048 Mode 2)
# ---------------------------------------------------------------------------


class TestInvocationComposition:
    """Verify the service routes through compose_name_invocation."""

    @pytest.mark.asyncio
    async def test_calls_compose_name_invocation(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """When no pipeline is wired, compose_name_invocation is still called (backward compat)."""
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        with patch(
            "narrare.generation.name_service.compose_name_invocation",
            new=AsyncMock(wraps=_identity_compose),
        ) as mock_compose:
            request = _default_request()
            await service.generate_names(request, user_id=uuid4())

        mock_compose.assert_awaited_once()
        args, _ = mock_compose.call_args
        assert len(args) >= 1
        # First positional arg is the pipeline (None in this fixture)
        assert args[0] is None

    @pytest.mark.asyncio
    async def test_calls_with_correct_project_id(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """The project_id from the request is forwarded to compose_name_invocation."""
        import uuid

        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        with patch(
            "narrare.generation.name_service.compose_name_invocation",
            new=AsyncMock(wraps=_identity_compose),
        ) as mock_compose:
            project_id = uuid.uuid4()
            request = _default_request(project_id=project_id)
            await service.generate_names(request, user_id=uuid4())

        kwargs = mock_compose.call_args.kwargs
        assert kwargs.get("project_id") == project_id

    @pytest.mark.asyncio
    async def test_calls_with_correct_language(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """The explanation_language from the request is forwarded as language."""
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        with patch(
            "narrare.generation.name_service.compose_name_invocation",
            new=AsyncMock(wraps=_identity_compose),
        ) as mock_compose:
            await service.generate_names(
                _default_request(explanation_language="de"), user_id=uuid4()
            )

        kwargs = mock_compose.call_args.kwargs
        assert kwargs.get("language") == "de"

    @pytest.mark.asyncio
    async def test_calls_with_prompt_context(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """The PromptContext built from request data is forwarded."""
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        with patch(
            "narrare.generation.name_service.compose_name_invocation",
            new=AsyncMock(wraps=_identity_compose),
        ) as mock_compose:
            request = _default_request(
                name_style="norse",
                name_type=NameType.PLACE,
                count=3,
                gender=GenderEnum.MALE,
                explanation_language="en",
            )
            await service.generate_names(request, user_id=uuid4())

        kwargs = mock_compose.call_args.kwargs
        ctx = kwargs.get("prompt_context")
        assert ctx is not None
        assert isinstance(ctx, PromptContext)
        assert ctx.language == "en"
        assert ctx.mode == "names"
        assert ctx.extra["name_style"] == "norse"
        assert ctx.extra["name_type"] == "place"

    @pytest.mark.asyncio
    async def test_calls_with_pipeline_when_provided(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """When an invocation_pipeline is wired, it is forwarded to compose_name_invocation."""
        from unittest.mock import MagicMock

        from narrare_core.ai_invocation.pipeline import InvocationPipeline

        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)
        pipeline = MagicMock(spec=InvocationPipeline)

        svc = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            model_resolution=_static_resolution(config),
            novel_repo=permissive_novel_repo(),
            kb_repo=None,
            invocation_pipeline=pipeline,
        )

        with patch(
            "narrare.generation.name_service.compose_name_invocation",
            new=AsyncMock(wraps=_identity_compose),
        ) as mock_compose:
            await svc.generate_names(_default_request(), user_id=uuid4())

        mock_compose.assert_awaited_once()
        args, _ = mock_compose.call_args
        assert len(args) >= 1
        assert args[0] is pipeline

    @pytest.mark.asyncio
    async def test_enriched_context_used_for_prompt(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
    ) -> None:
        """The PromptContext returned by compose_name_invocation is passed to composer.build()."""
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        with patch(
            "narrare.generation.name_service.compose_name_invocation",
            new=AsyncMock(wraps=_identity_compose),
        ):
            request = _default_request(explanation_language="fr")
            await service.generate_names(request, user_id=uuid4())

        # Verify composer received the enriched context (identical to original when None)
        mock_composer.build.assert_awaited_once()
        call_args = mock_composer.build.call_args
        # Second positional arg is the PromptContext
        composer_ctx = call_args[0][1] if len(call_args[0]) > 1 else None
        assert composer_ctx is not None
        assert composer_ctx.language == "fr"
        assert composer_ctx.mode == "names"
        assert composer_ctx.extra.get("name_type") == "character"


# ---------------------------------------------------------------------------
# Helper: identity compose_name_invocation for mocking
# ---------------------------------------------------------------------------


async def _identity_compose(
    pipeline: object,
    *,
    project_id: object,
    language: str,
    prompt_context: PromptContext,
) -> PromptContext:
    """Return the prompt context unchanged — mirrors pipeline=None behaviour."""
    return prompt_context
