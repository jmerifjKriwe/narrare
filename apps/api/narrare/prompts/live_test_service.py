"""PROMPT-003 optional live-test service (CR-AUFG-07-16).

Validates provider/secret gating + token-cost acknowledgement, resolves
the model via ``ModelRoutingResolver``, composes the system prompt via
the provider-free Core preview, then streams free-form output from
:class:`PromptLiveTestAgent` through the SSE event stream. Output is
NEVER persisted.

**Provider gating (architecture fit):**
   The resolver IS the gate — ``ModelRoutingResolverImpl.resolve()`` raises
   ``ConfigurationError`` when no provider is configured. This mirrors the
   writing endpoints (``deps_writing.py``). No separate ``ProviderGate``
   abstraction is introduced (RULE-07: reuse, don't invent).

**M2 (Core Spec Review):**
   ``PromptLiveTestAgent.run()`` bypasses base-class error classification,
   but ``run_stream()`` (used here) calls ``super().run_stream()`` and IS
   classified. As defense-in-depth, the SSE helper catches any exception
   that escapes classification and converts it to a typed SSE error event
   (RULE-11: never silent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

from narrare.prompts._live_test_sse import live_test_event_stream
from narrare.prompts.schemas_prompt_ux import LiveTestRequest, LiveTestStartedResponse
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.contracts import ContextSnapshot
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from pydantic_ai.models import Model

    from narrare_core.agents.prompt_live_test_agent import (
        PromptLiveTestAgent,
        PromptLiveTestDeps,
    )
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.prompts.contracts import PromptPreviewProtocol
    from narrare_core.prompts.preview_types import PromptPreview

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Provider-/model-surface Protocols — structural types matching the real
# implementations. Declared locally (ISP) so unit tests can supply Fakes
# without ``type: ignore`` (RULE-23).
# ---------------------------------------------------------------------------


@runtime_checkable
class _ModelResolver(Protocol):
    """Minimal surface of ``ModelRoutingResolver`` needed by this service."""

    async def resolve(
        self,
        intent: LLMIntent,
        user_id: UUID,
        project_id: UUID | None,
    ) -> ResolvedModel: ...


@runtime_checkable
class _ModelRegistry(Protocol):
    """Minimal surface of ``ModelRegistry`` needed by this service."""

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = ...,
        base_url: str | None = ...,
    ) -> Model: ...


@runtime_checkable
class _AgentFactory(Protocol):
    """Callable that builds a ``PromptLiveTestAgent`` from a resolved Model."""

    def __call__(self, *, model: Model) -> PromptLiveTestAgent: ...


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PromptLiveTestApiService:
    """Backend live-test orchestration (PROMPT-003).

    Orchestrates: gating → model resolution → prompt composition →
    agent streaming → SSE framing. All dependencies are injected so the
    service is fully testable with Fakes (no LLM, no DB).

    Args:
        resolver: Model routing resolver — the provider gate. Raises
            ``ConfigurationError`` when no provider is configured.
        registry: ModelRegistry — builds the pydantic-ai Model from the
            resolved config + credentials.
        preview: Core ``PromptPreviewProtocol`` — composes the system
            prompt (provider-free) so the live test uses the real
            cascade-resolved prompt unless ``edited_override`` is set.
        agent_factory: Callable that instantiates ``PromptLiveTestAgent``
            from a resolved Model.
        intent: Default ``LLMIntent`` for model routing. Prompt
            customization live-test is a global "vibe check", not tied to
            a specific project, so ``LLMIntent.WRITE`` is a sensible default.
        rate_limit_budget: Max requests/minute (informational — the route
            layer enforces via ``AI_PROMPT_LIVE_TEST_LIMITER``). Surfaced
            in ``LiveTestStartedResponse.rate_limit_remaining``.
    """

    def __init__(
        self,
        *,
        resolver: _ModelResolver,
        registry: _ModelRegistry,
        preview: PromptPreviewProtocol,
        agent_factory: _AgentFactory,
        intent: LLMIntent = LLMIntent.WRITE,
        rate_limit_budget: int = 5,
    ) -> None:
        self._resolver = resolver
        self._registry = registry
        self._preview = preview
        self._agent_factory = agent_factory
        self._intent = intent
        self._rate_limit_budget = rate_limit_budget

    async def validate_live_test(
        self,
        prompt_id: str,
        request: LiveTestRequest,
        *,
        user_id: str,
    ) -> LiveTestStartedResponse:
        """Validate provider gating + token-cost acknowledgement.

        Args:
            prompt_id: Prompt identifier in ``{category}/{language}/{mode}`` form.
            request: Live-test request body (variables + locale + acknowledgement).
            user_id: Authenticated user identifier.

        Returns:
            ``LiveTestStartedResponse`` with resolved model_id + remaining budget.

        Raises:
            ValidationError: ``acknowledge_token_cost`` is False.
            ConfigurationError: No provider configured (from resolver).
        """
        if not request.acknowledge_token_cost:
            raise ValidationError(
                "acknowledge_token_cost must be true",
                code="TOKEN_COST_NOT_ACKNOWLEDGED",
            )

        from uuid import UUID

        resolved = await self._resolver.resolve(self._intent, UUID(user_id), None)
        return LiveTestStartedResponse(
            prompt_id=prompt_id,
            intent=_intent_label_for(prompt_id),
            model_id=resolved.config.model_id,
            rate_limit_remaining=max(0, self._rate_limit_budget - 1),
        )

    async def stream_live_test(
        self,
        prompt_id: str,
        request: LiveTestRequest,
        *,
        user_id: str,
        metadata: LiveTestStartedResponse,
    ) -> AsyncIterator[str]:
        """Stream SSE frames for the live-test output.

        Args:
            prompt_id: Prompt identifier in ``{category}/{language}/{mode}`` form.
            request: Live-test request body.
            user_id: Authenticated user identifier.
            metadata: Validated start metadata returned by ``validate_live_test``.

        Yields:
            SSE-formatted event strings (meta / delta / done / [DONE]).

        Raises (before any SSE frame is yielded):
            ConfigurationError: No provider configured (from resolver).
            ValidationError: ``acknowledge_token_cost`` is False.

        After the first frame is yielded, errors surface as SSE error
        events (see :func:`live_test_event_stream`).
        """
        from uuid import UUID

        # Gate + model resolution — raises before SSE if no provider.
        resolved = await self._resolver.resolve(self._intent, UUID(user_id), None)
        model = await self._registry.get_model(
            resolved.config,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        )
        agent = self._agent_factory(model=model)

        # Compose the system prompt via the provider-free Core preview.
        # When edited_override is set, the preview surfaces the override;
        # otherwise the cascade-resolved bundled prompt is used.
        snapshot = _build_snapshot(request)
        preview_result: PromptPreview = await self._preview.preview(
            prompt_id=prompt_id,
            snapshot=snapshot,
            edited_override=request.edited_override,
        )

        deps = _build_deps(request, preview_result.system_prompt)
        logger.info(
            "prompt_live_test_started",
            prompt_id=prompt_id,
            model_id=resolved.config.model_id,
            source=resolved.source,
        )

        async for frame in live_test_event_stream(
            _agent_text_stream(agent, request.user_prompt, deps),
            metadata=metadata,
        ):
            yield frame


# ---------------------------------------------------------------------------
# Module-private helpers — kept here (not in __init__) for testability.
# ---------------------------------------------------------------------------


def _intent_label_for(prompt_id: str) -> str:
    """Derive the intent label (prompt category) from the prompt_id."""
    return prompt_id.split("/")[0] if "/" in prompt_id else prompt_id


def _build_snapshot(request: LiveTestRequest) -> ContextSnapshot:
    """Build a Core ``ContextSnapshot`` from the live-test request."""
    return ContextSnapshot(
        variables=dict(request.variables),
        language=request.language,
        genre=request.genre,
        mode=request.mode,
    )


def _build_deps(
    request: LiveTestRequest,
    composed_system: str,
) -> PromptLiveTestDeps:
    """Build ``PromptLiveTestDeps`` for the agent run.

    The composed system prompt comes from the provider-free preview
    (cascade-resolved or the edited override). The user message is the
    raw ``user_prompt`` from the request.
    """
    from narrare_core.agents.prompt_live_test_agent import PromptLiveTestDeps

    return PromptLiveTestDeps(
        composed_system=composed_system,
        composed_user=request.user_prompt,
        language=request.language,
    )


async def _agent_text_stream(
    agent: PromptLiveTestAgent,
    user_prompt: str,
    deps: PromptLiveTestDeps,
) -> AsyncIterator[str]:
    """Convert ``StreamEvent`` objects from the agent to text chunks.

    The agent's ``run_stream`` yields ``StreamEvent`` events; the SSE
    helper expects an async iterator of raw text chunks. This adapter
    extracts ``event.text`` from token events. Done/error events carry
    no additional text for the SSE layer.
    """
    async for event in agent.run_stream(prompt=user_prompt, deps=deps):
        if event.type == "token":
            yield event.text
