"""Shared fakes/helpers for StoryboardService tests (ADR-086 L21).

Mirrors ``_character_arc_test_helpers.py`` (L20 convention):

- ``make_static_resolution`` covers the mechanical ctor migration of the
  existing fixtures to ``StaticModelResolution`` (ADR-086 regression
  contract #4 — outcomes unchanged).
- ``make_resolved_model`` builds the canned triple the routing cascade
  would return, used by both static and counting resolutions.
"""

from __future__ import annotations

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel

_CASCADE_CONFIG = ResolvedModelConfig(
    provider_name="zai",
    model_id="glm-4.7",
    temperature=0.7,
)


def make_resolved_model(**kw: str | None) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=_CASCADE_CONFIG,
        api_key=kw.get("api_key"),
        base_url=kw.get("base_url"),
        source="unit-test",
    )


def make_static_resolution(**kw: str | None) -> StaticModelResolution:
    """A ``StaticModelResolution`` over a canned triple — fixture shim."""
    return StaticModelResolution(make_resolved_model(**kw))
