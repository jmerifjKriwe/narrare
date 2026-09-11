"""Extraction context helpers — existing KB entry fetch + prompt context.

Extracted from ``extraction_service.py`` for RULE-04 compliance (hard
300-line service limit). Owns the extraction prompt-context data path:
the existing-entries fetch (dedup names, entity ID roster, curated world
context) and the ``PromptContext`` assembly. The LLM orchestration stays
in the service.

See:
    :class:`narrare.kb.extraction_service.ExtractionService`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry

logger = structlog.get_logger(__name__)


async def fetch_existing_entries(
    kb_repo: KBRepositoryProtocol,
    novel_id: UUID,
    user_id: UUID,
) -> list[KBEntry]:
    """Fetch existing KB entries for the novel (dedup + world context).

    Repository errors propagate — error-tolerant callers should use
    :func:`fetch_existing_entries_graceful`.
    """
    entries, _ = await kb_repo.list_entries(
        novel_id=novel_id,
        entity_type=None,
        tags=None,
        page=1,
        page_size=1000,
    )
    return list(entries)


async def get_existing_entity_names(
    kb_repo: KBRepositoryProtocol,
    novel_id: UUID,
    user_id: UUID,
) -> list[str]:
    """Fetch existing KB entry names for dedup.

    Thin wrapper over :func:`fetch_existing_entries` retained as the dedup
    names accessor. Repository errors propagate — error-tolerant callers
    should use :func:`fetch_existing_entries_graceful`.
    """
    entries = await fetch_existing_entries(kb_repo, novel_id, user_id)
    return [entry.name for entry in entries if entry.name]


def format_entity_roster(entries: list[KBEntry]) -> str:
    """Render KB entries as the typed entity ID roster for the prompt.

    Each line has the format ``- {name} ({entity_type}) [id={id}]`` — the
    bracketed ID is the machine-referenceable ``target_entity_id`` for
    ``update_entity`` items (entity resolution, KB-007). The roster is
    rendered from the complete entry list (no cap): it is the reference
    the extraction agent resolves mentions against.

    Field access is best-effort (``getattr``): a partial entry degrades to
    its name line rather than crashing the caller, mirroring
    :func:`narrare.kb._world_context.format_world_context`. Entries without
    a usable name are skipped.

    Args:
        entries: KB entries to render (complete list, uncapped).

    Returns:
        The formatted roster, or an empty string when ``entries`` is empty.
    """
    lines: list[str] = []
    for entry in entries:
        name = getattr(entry, "name", None)
        if not name:
            continue
        entity_type = getattr(entry, "entity_type", "") or ""
        entry_id = getattr(entry, "id", None)
        id_part = f" [id={entry_id}]" if entry_id else ""
        lines.append(f"- {name} ({entity_type}){id_part}")
    return "\n".join(lines)


def build_extraction_prompt_context(
    *,
    chapter_title: str,
    existing_entity_roster: str,
    world_context: str = "",
) -> PromptContext:
    """Build the PromptContext for the extraction prompt (RULE-02).

    ``existing_entity_roster`` carries the pre-rendered typed ID roster
    (``- name (type) [id=...]`` lines from :func:`format_entity_roster`);
    it is bound to the registered ``existing_entity_names`` SYSTEM_VAR
    (RULE-22 — variable key unchanged, rendered content enriched).
    Composition happens via ``compose_invocation`` in the caller; the
    Narrare meta-prompt is injected automatically by NarrareMeta
    Capability (ADR-026).
    """
    return PromptContext(
        language="en",
        mode="extract",
        chapter_title=chapter_title,
        extra={
            "existing_entity_names": existing_entity_roster,
            "world_context": world_context,
        },
    )


async def fetch_existing_entries_graceful(
    kb_repo: KBRepositoryProtocol,
    novel_id: UUID,
    user_id: UUID,
) -> list[KBEntry]:
    """Fetch existing KB entries with graceful degradation (RULE-11).

    If the KB repo is unavailable (DB connection lost, timeout, etc.),
    returns an empty list so extraction can proceed without dedup data
    or world context. Logs a warning so the failure is visible.
    """
    try:
        return await fetch_existing_entries(kb_repo, novel_id, user_id)
    except Exception as exc:
        logger.warning(
            "kb_repo_unavailable_using_empty_dedup",
            novel_id=str(novel_id),
            error=str(exc),
        )
        return []
