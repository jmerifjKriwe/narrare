"""Unit tests for the operator-plane env pins (finding #7).

Covers the pin derivation from the benchmark llm config: both
system-default model pins carry the configured model, each keyed
provider maps to ITS ``CoreSettings`` fallback var (ADR-071 §3), and
key-less providers (``ollama``, unknown ids — the latter rejected
upstream by ``parse_sections``) produce no key pin. The hybrid-stack
wiring (spawn env + no-leak on failure paths) is verified in
``test_stack_hybrid.py``.
"""

from __future__ import annotations

from typing import Final

import pytest

from benchmark.config_schemas import LlmConfig
from benchmark.stack_operator_env import operator_env_pins

FAKE_MODEL: Final[str] = "wizard-model-id"
FAKE_KEY: Final[str] = "sk-fake-operator-key"
FAKE_OLLAMA_URL: Final[str] = "http://localhost:11434"


def _llm(provider: str) -> LlmConfig:
    return LlmConfig(provider, FAKE_KEY, FAKE_MODEL, FAKE_OLLAMA_URL, "general")


@pytest.mark.parametrize(
    ("provider", "key_var"),
    [
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("google", "GOOGLE_API_KEY"),
        ("groq", "GROQ_API_KEY"),
        ("openrouter", "OPENROUTER_API_KEY"),
        ("zai", "ZAI_API_KEY"),
    ],
)
def test_keyed_provider_maps_to_its_core_settings_fallback_var(provider: str, key_var: str) -> None:
    pins = operator_env_pins(_llm(provider))
    assert pins[key_var] == FAKE_KEY


@pytest.mark.parametrize("provider", ["ollama", "no-such-provider"])
def test_keyless_provider_gets_no_key_pin(provider: str) -> None:
    pins = operator_env_pins(_llm(provider))
    assert not any(name.endswith("_API_KEY") for name in pins)


@pytest.mark.parametrize("provider", ["anthropic", "ollama"])
def test_both_system_default_categories_pinned_to_configured_model(provider: str) -> None:
    pins = operator_env_pins(_llm(provider))
    assert pins["DEFAULT_ANALYSIS_MODEL"] == FAKE_MODEL
    assert pins["DEFAULT_WRITING_MODEL"] == FAKE_MODEL


def test_pin_names_exactly_model_pins_plus_at_most_one_key_var() -> None:
    """Exact key set — the pins introduce no other env surface."""
    assert set(operator_env_pins(_llm("zai"))) == {
        "DEFAULT_ANALYSIS_MODEL",
        "DEFAULT_WRITING_MODEL",
        "ZAI_API_KEY",
    }
    assert set(operator_env_pins(_llm("ollama"))) == {
        "DEFAULT_ANALYSIS_MODEL",
        "DEFAULT_WRITING_MODEL",
    }
