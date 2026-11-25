"""The prompt registry: the one prompt authority beside the allocator.

The registry (:mod:`app.kernel.prompts.registry`) holds every bundled prompt
spec — key, Jinja template, sample-variable factory, contract, novel scope —
the sandboxed render (:mod:`app.kernel.prompts.rendering`) turns a source into
text, refusing every failure by name, and :func:`render` walks the effective
chain (novel row → user-global row → bundled) to pick that source, includes
following. Later work docks the five bundled prompts and the user-facing
overrides onto this; nothing else enters here.
"""

from app.kernel.prompts.registry import (
    REASONS,
    AssembledContext,
    LiveContextMissingError,
    LiveTestContext,
    PromptRegistry,
    PromptRenderError,
    PromptSpec,
    get_registry,
)
from app.kernel.prompts.rendering import (
    MAX_INCLUDE_DEPTH,
    referenced_names,
    render,
    render_source,
)


def no_includes(key: str) -> str:
    """The include chain for a bundled-only render: every include is missing."""
    raise KeyError(key)


__all__ = [
    "MAX_INCLUDE_DEPTH",
    "REASONS",
    "AssembledContext",
    "LiveContextMissingError",
    "LiveTestContext",
    "PromptRegistry",
    "PromptRenderError",
    "PromptSpec",
    "get_registry",
    "referenced_names",
    "render",
    "render_source",
]
