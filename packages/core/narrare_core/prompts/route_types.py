"""Prompt route contract value objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptRoute:
    """Resolved PromptComposer route."""

    category: str
    mode: str
    required_variables: frozenset[str] = frozenset()
    optional_variables: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class PromptRouteConfig:
    """Routeability contract for one LLM intent."""

    category: str
    default_mode: str | None
    required_variables: frozenset[str] = frozenset()
    optional_variables: frozenset[str] = frozenset()
    allowed_context_modes: frozenset[str] = frozenset()
