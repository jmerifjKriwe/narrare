"""Chapter frontmatter consumer of the KB entity lifecycle (ADR-050 P1-B).

Specialisation of :class:`KBEntityLifecycleObserver` for chapter
frontmatter (WRITE-001 / KB-001). Frontmatter references KB entities
via structured keys but is user-authored content, so this consumer
NEVER rewrites on rename/deprecate/delete — it only surfaces stale or
dangling references as :class:`RefIntegrityIssue` records.

Extracted from the former monolithic ``integration_contracts.py`` per
RULE-04. Base Protocol in :mod:`._kb_lifecycle`; vocabulary in
:mod:`._vocab`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from narrare_core.context.integration_contracts._kb_lifecycle import KBEntityLifecycleObserver


@runtime_checkable
class ChapterFrontmatterRefConsumer(KBEntityLifecycleObserver, Protocol):
    """Specialisation for chapter frontmatter (WRITE-001 / KB-001).

    Frontmatter references KB entities via keys ``pov_character``,
    ``characters``, ``location``, ``locations``, ``faction``,
    ``factions``, ``system``, ``systems``, ``timeline``,
    ``timelines``. Values may be entity ids (preferred) or names
    (legacy/free-form). Frontmatter is user-authored content
    (RULE-22 §6: ``_USER_CONTENT_VARS`` includes ``chapter_text``
    but frontmatter is structured data on the chapter itself —
    rename/delete MUST NOT auto-rewrite it).

    Required behaviour:

    * ``on_kb_entity_renamed``: never rewrite frontmatter. Emit
      :class:`RefIntegrityIssue` with reason ``stale_name_ref`` for
      each name-based ref that no longer matches.
    * ``on_kb_entity_deprecated``: emit a warning issue. Frontmatter
      continues to reference the deprecated entity until the user
      explicitly updates it.
    * ``on_kb_entity_deleted``: emit an error issue
      (``deleted_ref_without_tombstone``). Future writes that try to
      consume the frontmatter ref will be unable to resolve it.
    """

    @property
    def consumer_feature(self) -> str:
        return "chapter_frontmatter"
        ...
