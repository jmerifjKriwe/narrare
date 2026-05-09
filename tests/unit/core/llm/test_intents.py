"""Tests for llm/intents.py"""

from __future__ import annotations

import pytest

from narrare_core.llm.intents import LLMIntent, get_model_config, MODEL_ROUTING


class TestLLMIntent:
    def test_all_intents_have_routing_entry(self) -> None:
        """Every intent except EMBED must have a model routing entry."""
        for intent in LLMIntent:
            if intent == LLMIntent.EMBED:
                continue
            assert intent in MODEL_ROUTING, (
                f"LLMIntent.{intent.name} has no entry in MODEL_ROUTING. "
                "Add one in llm/intents.py."
            )

    def test_get_model_config_returns_config(self) -> None:
        config = get_model_config(LLMIntent.WRITE)
        assert config.model
        assert 0.0 <= config.temperature <= 1.0
        assert config.max_tokens > 0

    def test_get_model_config_raises_for_embed(self) -> None:
        with pytest.raises(KeyError):
            get_model_config(LLMIntent.EMBED)

    def test_streaming_intents_have_streams_true(self) -> None:
        """Writing intents should support streaming."""
        assert MODEL_ROUTING[LLMIntent.WRITE].streams is True
        assert MODEL_ROUTING[LLMIntent.EXTEND].streams is True
        assert MODEL_ROUTING[LLMIntent.KB_CREATE].streams is True
