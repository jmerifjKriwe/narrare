"""Central SQLAlchemy model registry.

Imports ALL ORM models to ensure they are registered with ``Base.metadata``
before any request is processed.  This is required because some models
declare foreign keys to tables defined in other modules (e.g.
``ChapterVersion.generation_request_id`` → ``generation_requests.id``).
Without this registry, those FKs would fail at flush time with
``NoReferencedTableError`` if the target model's module was never imported.

This module MUST be imported early in the application lifecycle —
typically inside ``create_app()`` — before any database operation.
"""

# pyright: reportUnusedImport=false

from __future__ import annotations

# ── Auth ──
from narrare.auth.models import User  # noqa: F401

# ── Chapters (includes ChapterVersion with FK to generation_requests) ──
from narrare.chapters.models import Chapter, ChapterVersion  # noqa: F401

# ── Embeddings ──
from narrare.embeddings.models import ContextUsageEvent, Embedding  # noqa: F401

# ── Generation / Graph Runs ──
from narrare.generation.models import GraphRun  # noqa: F401

# ── KB ──
from narrare.kb.models import KBEntry, KBRelationship  # noqa: F401

# ── Memory / Feedback ──
from narrare.memory.models import FeedbackEventModel, PreferenceProfileModel  # noqa: F401

# ── Novels ──
from narrare.novels.models import Novel  # noqa: F401

# ── Planning ──
from narrare.planning.models import ChapterOutline  # noqa: F401

# ── Prompts (prompt_revisions history table — CR-AUFG-07-19) ──
from narrare.prompts.models import PromptRevision  # noqa: F401

# ── Series ──
from narrare.series.models import Series, SeriesSettings  # noqa: F401

# ── Settings ──
from narrare.settings.models import (  # noqa: F401
    ProjectSettings,
    UserAiSettings,
    UserProvider,
    UserSettings,
)

# ── Settings / Token limits ──
from narrare.settings.token_limits.models import ProjectTokenLimits, UserTokenLimits  # noqa: F401

# ── Templates ──
from narrare.templates.models import KBTemplate  # noqa: F401

# ── Volumes ──
from narrare.volumes.models import Volume  # noqa: F401

# ── Writing (includes GenerationRequest — required by ChapterVersion FK) ──
from narrare.writing.models import GenerationRequest  # noqa: F401
