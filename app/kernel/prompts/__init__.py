"""The prompt registry: the one prompt authority beside the allocator.

The registry (:mod:`app.kernel.prompts.registry`) holds every bundled prompt
spec — key, Jinja template, sample-variable factory, contract, novel scope —
the sandboxed render (:mod:`app.kernel.prompts.render`) turns a source into
text, refusing every failure by name, and :func:`render` walks the effective
chain (novel row → user-global row → bundled) to pick that source, includes
following. Later work docks the four bundled prompts and the user-facing
overrides onto this; nothing else enters here.
"""

from app.kernel.prompts.registry import (
    REASONS,
    PromptRegistry,
    PromptRenderError,
    PromptSpec,
    get_registry,
)
from app.kernel.prompts.render import MAX_INCLUDE_DEPTH, render, render_source

__all__ = [
    "MAX_INCLUDE_DEPTH",
    "REASONS",
    "PromptRegistry",
    "PromptRenderError",
    "PromptSpec",
    "get_registry",
    "render",
    "render_source",
]
