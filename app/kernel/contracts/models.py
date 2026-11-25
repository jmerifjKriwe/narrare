"""Shared domain vocabulary. Two capabilities need these, so they live here.

This module is a thin aggregator: the actual definitions live in
``user.py``, ``novel.py``, ``series.py`` and ``knowledge.py``. It is kept (and its import
path) so existing callers and ``register_models()`` continue to work; new
models should be added to the per-domain module, not here.
"""

from app.kernel.contracts.knowledge import (
    ENTITY_TYPES,
    MAX_RELATIONS,
    Chunk,
    ConsistencyFinding,
    Document,
    Entity,
    EntityRelation,
    EntitySuggestion,
)
from app.kernel.contracts.novel import (
    AI_ROLES,
    AUTHOR_TYPOLOGIES,
    CANON_STRICTNESS_MAX,
    CANON_STRICTNESS_MIN,
    DRAMATIC_FORM_MAX_LENGTH,
    WORD_GOAL_MAX,
    WORD_GOAL_MIN,
    Chapter,
    Novel,
    Scene,
)
from app.kernel.contracts.series import Series
from app.kernel.contracts.user import User

__all__ = [
    "AI_ROLES",
    "AUTHOR_TYPOLOGIES",
    "CANON_STRICTNESS_MAX",
    "CANON_STRICTNESS_MIN",
    "DRAMATIC_FORM_MAX_LENGTH",
    "ENTITY_TYPES",
    "MAX_RELATIONS",
    "WORD_GOAL_MAX",
    "WORD_GOAL_MIN",
    "Chapter",
    "Chunk",
    "ConsistencyFinding",
    "Document",
    "Entity",
    "EntityRelation",
    "EntitySuggestion",
    "Novel",
    "Scene",
    "Series",
    "User",
]
