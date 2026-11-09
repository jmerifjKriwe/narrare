"""Shared domain vocabulary. Two capabilities need these, so they live here.

This module is a thin aggregator: the actual definitions live in
``user.py``, ``novel.py`` and ``knowledge.py``. It is kept (and its import
path) so existing callers and ``register_models()`` continue to work; new
models should be added to the per-domain module, not here.
"""

from app.kernel.contracts.knowledge import (
    ENTITY_TYPES,
    Chunk,
    ConsistencyFinding,
    Document,
    Entity,
    EntityRelation,
    EntitySuggestion,
)
from app.kernel.contracts.novel import Chapter, Novel
from app.kernel.contracts.user import User

__all__ = [
    "ENTITY_TYPES",
    "Chapter",
    "Chunk",
    "ConsistencyFinding",
    "Document",
    "Entity",
    "EntityRelation",
    "EntitySuggestion",
    "Novel",
    "User",
]
