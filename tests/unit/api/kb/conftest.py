"""Shared pytest fixtures for KBAssistService tests.

Fixtures are defined here so both ``test_assist_service.py`` and
``test_assist_service_fallback.py`` discover them without duplication
(RULE-04: modularize rather than compress).
"""

from __future__ import annotations

import pytest

from narrare_core.agents.kb_assist_agent import KBAssistDeps
from narrare_core.agents.kb_assist_types import KBAssistOutput
from narrare_core.llm import ResolvedModelConfig

from ._assist_fakes import (
    FakeComposer,
    FakeModelRegistry,
    FakeProactiveContext,
)


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test", model_id="test-model", temperature=0.7, max_tokens=4096
    )


@pytest.fixture
def registry() -> FakeModelRegistry:
    return FakeModelRegistry()


@pytest.fixture
def proactive_context() -> FakeProactiveContext:
    return FakeProactiveContext()


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def deps() -> KBAssistDeps:
    return KBAssistDeps(
        language="en",
        entity_type="character",
        template_structure={"name": "Name"},
    )


@pytest.fixture
def agent_output() -> KBAssistOutput:
    return KBAssistOutput(
        mode="question",
        question="What is the character's name?",
        field_key="name",
    )
