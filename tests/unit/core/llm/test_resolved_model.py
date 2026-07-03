"""Tests for ResolvedModel / ResolvedModelConfig recommended_tier defaults.

Covers backward compatibility. Pure dataclass tests (no resolver, no DB). Kept in
``core`` because they import only ``narrare_core.*`` and therefore collect cleanly
under the MutMut ``core`` sandbox, which does not include the ``narrare`` (API)
package.

Split from the former ``test_model_routing_tier.py`` for RULE-06 (one
responsibility per file): the dataclass-shape tests stay in core, while the
resolver-backed ``recommended_tier`` propagation tests live in
``tests/unit/api/settings/test_model_routing_tier.py``.
"""

from __future__ import annotations


class TestResolvedModelDataclass:
    """Verify ResolvedModel fields, defaults, and backward compatibility."""

    def test_recommended_tier_defaults_to_none(self) -> None:
        """recommended_tier is optional and defaults to None."""
        from narrare_core.llm.model_config import ResolvedModelConfig
        from narrare_core.llm.model_routing import ResolvedModel

        config = ResolvedModelConfig(
            provider_name="openai",
            model_id="gpt-4o",
        )
        model = ResolvedModel(config=config)
        assert model.recommended_tier is None

    def test_recommended_tier_can_be_set(self) -> None:
        """recommended_tier can be explicitly provided."""
        from narrare_core.llm.model_config import ResolvedModelConfig
        from narrare_core.llm.model_routing import ResolvedModel

        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
        )
        model = ResolvedModel(config=config, recommended_tier="creative")
        assert model.recommended_tier == "creative"

    def test_backward_compatible_without_recommended_tier(self) -> None:
        """Existing code that doesn't pass recommended_tier still works."""
        from narrare_core.llm.model_config import ResolvedModelConfig
        from narrare_core.llm.model_routing import ResolvedModel

        config = ResolvedModelConfig(
            provider_name="openai",
            model_id="gpt-4o",
        )
        # Old-style construction — no recommended_tier
        model = ResolvedModel(
            config=config,
            api_key="sk-test",
            base_url=None,
            source="user_default",
        )
        assert model.config.model_id == "gpt-4o"
        assert model.source == "user_default"
        assert model.recommended_tier is None
