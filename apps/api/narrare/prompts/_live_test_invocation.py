"""Invocation-support helpers for the PROMPT-003 live-test service.

Extracted from ``live_test_service.py`` to respect RULE-04's 300-line
service limit after the Task-7 ``ModelRegistry.prepare()`` migration
(mirrors the domain's ``_live_test_sse.py`` extraction precedent).
Owns: snapshot/deps building for the agent run, the agent text-stream
adapter, and the intent-label derivation.

The module is private (``_``-prefixed, mirroring
``_live_test_sse.py``); its functions are public within it and
consumed only by ``live_test_service.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.prompts.contracts import ContextSnapshot

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits

    from narrare.prompts.schemas_prompt_ux import LiveTestRequest
    from narrare_core.agents.prompt_live_test_agent import (
        PromptLiveTestAgent,
        PromptLiveTestDeps,
    )


def intent_label_for(prompt_id: str) -> str:
    """Derive the intent label (prompt category) from the prompt_id."""
    return prompt_id.split("/")[0] if "/" in prompt_id else prompt_id


def build_snapshot(request: LiveTestRequest) -> ContextSnapshot:
    """Build a Core ``ContextSnapshot`` from the live-test request."""
    return ContextSnapshot(
        variables=dict(request.variables),
        language=request.language,
        genre=request.genre,
        mode=request.mode,
    )


def build_deps(
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


async def agent_text_stream(
    agent: PromptLiveTestAgent,
    user_prompt: str,
    deps: PromptLiveTestDeps,
    *,
    model_settings: ModelSettings | None = None,
    usage_limits: UsageLimits | None = None,
) -> AsyncIterator[str]:
    """Convert ``StreamEvent`` objects from the agent to text chunks.

    The agent's ``run_stream`` yields ``StreamEvent`` events; the SSE
    helper expects an async iterator of raw text chunks. This adapter
    extracts ``event.text`` from token events. Done/error events carry
    no additional text for the SSE layer.

    ``model_settings``/``usage_limits`` come from the coherent
    ``ModelRegistry.prepare()`` triple and are forwarded to the
    underlying pydantic-ai stream.
    """
    async for event in agent.run_stream(
        prompt=user_prompt,
        deps=deps,
        model_settings=model_settings,
        usage_limits=usage_limits,
    ):
        if event.type == "token":
            yield event.text
