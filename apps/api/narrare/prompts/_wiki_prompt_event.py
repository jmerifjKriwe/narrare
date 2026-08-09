"""Wiki prompt-change event helper (Q-016).

Extracted from ``history_service.py`` per RULE-04 (file-size limit). This
module owns the single responsibility of publishing a ``wiki.prompt.changed``
event when a wiki-category prompt override changes — bridging the prompt
cascade (global, no novel dimension) to the wiki-summary regeneration chain.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare_core.events.types import EventType

if TYPE_CHECKING:
    from narrare.events.publisher import EventPublisher

logger = structlog.get_logger(__name__)

# prompt_id format is ``{category}/{language}/{mode}``; wiki generation
# prompts live under the ``wiki/`` category. An override to one of them
# changes the wiki generation prompt globally, so wiki summaries regenerate.
WIKI_PROMPT_CATEGORY_PREFIX = "wiki/"


async def publish_wiki_prompt_changed(
    publisher: EventPublisher,
    prompt_id: str,
    content_hash: str,
) -> None:
    """Publish ``wiki.prompt.changed`` for a wiki-category override.

    Prompts are GLOBAL (cascade ``{category}/{language}/{mode}``, no novel
    dimension), so the event carries NO ``novel_id`` — the listener marks all
    novels' summaries stale (mark-all-across-novels, Q-016 decision).

    Args:
        publisher: The in-process ``EventPublisher`` (``app.state``).
        prompt_id: The overridden prompt id (must be wiki-category).
        content_hash: The override content hash (traceability fingerprint;
            the global mark-all is unconditional, so this is informational).
    """
    try:
        await publisher.publish(
            EventType.WIKI_PROMPT_CHANGED,
            aggregate_id=uuid.uuid5(uuid.NAMESPACE_URL, f"wiki-prompt:{prompt_id}"),
            payload={"prompt_version": content_hash, "prompt_id": prompt_id},
        )
    except Exception:
        logger.warning(
            "wiki_prompt_changed_publish_failed",
            prompt_id=prompt_id,
            exc_info=True,
        )
