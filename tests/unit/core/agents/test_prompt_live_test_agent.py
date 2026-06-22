"""Tests for the PROMPT-003 live-test agent."""

from __future__ import annotations

# narrare: allow reason="agent unit tests use TestModel instead of real LLM"
from pydantic_ai.models.test import TestModel

from narrare_core.agents.prompt_live_test_agent import (
    PromptLiveTestAgent,
    PromptLiveTestDeps,
    PromptLiveTestResult,
)


async def test_live_test_agent_returns_free_form_text() -> None:
    model = TestModel(custom_output_text="Once upon a time, the KB shaped the prose.")
    agent = PromptLiveTestAgent(model=model)
    deps = PromptLiveTestDeps(
        composed_system="You are a narrator.",
        composed_user="Continue the chapter.",
        language="en",
    )

    result = await agent.run(prompt=deps.composed_user, deps=deps)

    assert isinstance(result, PromptLiveTestResult)
    assert result.text.startswith("Once upon a time")


async def test_live_test_agent_streams_free_form_text() -> None:
    model = TestModel(custom_output_text="Streamed prose shaped by the resolved prompt.")
    agent = PromptLiveTestAgent(model=model)
    deps = PromptLiveTestDeps(
        composed_system="You are a narrator.",
        composed_user="Continue the chapter.",
        language="en",
    )

    chunks: list[str] = []
    async for event in agent.run_stream(prompt=deps.composed_user, deps=deps):
        if event.type == "token":
            chunks.append(event.text)

    assert "".join(chunks).startswith("Streamed prose")
