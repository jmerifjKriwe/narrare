"""KB lifecycle dispatcher — write-side observer hook (ADR-050 P1-B).

Thin collaborator injected into ``KBService``. On rename/deprecate/delete
the service calls the matching ``notify_*`` method; the dispatcher fans
the typed call out to every registered
:class:`KBEntityLifecycleObserver`.

Architectural decision — synchronous in-process observers, NOT Redis
Pub/Sub (ADR-012): see module docstring of the wiring module
``kb/lifecycle_dependencies.py`` and the ADR-050 Decision 2 rationale.
The short version: the Core Protocol carries typed kwargs
(``old_name``/``new_name``/``entity_id``) that an untyped Redis payload
would erase, the Timeline consumer performs a write-side mutation that
must share the request's DB session, and ADR-050 explicitly specifies
"KB calls every registered observer." ADR-012 remains the mechanism for
decoupled background work (embeddings, wiki regen) — a different
concern; the two systems coexist without conflict.

RULE-11 isolation: a single observer raising is logged and does not
block the remaining observers or roll back the KB mutation. This mirrors
``events/publisher.py`` ``_dispatch`` semantics and ADR-050 Option B's
"one consumer failure produces a ``RefIntegrityIssue``, not a rollback."
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare_core.context.integration_contracts import KBEntityLifecycleObserver

logger = structlog.get_logger(__name__)


class KBLifecycleDispatcher:
    """Fans KB lifecycle events out to registered observers.

    Args:
        observers: Registered ``KBEntityLifecycleObserver`` instances.
            Order is preserved; order is not semantically significant.
            May be empty (e.g. in tests or features with no consumers).
    """

    def __init__(self, observers: Sequence[KBEntityLifecycleObserver]) -> None:
        self._observers: Sequence[KBEntityLifecycleObserver] = tuple(observers)

    async def dispatch_kb_update(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
        old_name: str,
        was_deprecated: bool,
        new_name: str | None,
        new_status: str | None,
    ) -> None:
        """Inspect a KB update's intended values and fire the matching events.

        Centralises the rename/deprecate detection so ``KBService.update``
        stays a thin caller (RULE-04: keep ``service.py`` within its line
        budget). A rename fires only when the name actually changes; a
        deprecate fires only on the active→deprecated transition.

        Args:
            novel_id: Novel the entity belongs to.
            entity_id: The KB entry that was updated.
            old_name: Name before the update (snapshot before mutation).
            was_deprecated: Whether ``status`` was already ``deprecated``.
            new_name: Requested new name, or ``None`` if unchanged.
            new_status: Requested new status, or ``None`` if unchanged.
        """
        if new_name is not None and new_name != old_name:
            await self.notify_renamed(
                novel_id=novel_id,
                entity_id=entity_id,
                old_name=old_name,
                new_name=new_name,
            )
        if new_status == "deprecated" and not was_deprecated:
            await self.notify_deprecated(novel_id=novel_id, entity_id=entity_id)

    async def notify_renamed(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
        old_name: str,
        new_name: str,
    ) -> None:
        """Notify every observer of a KB entity name change."""
        for observer in self._observers:
            try:
                await observer.on_kb_entity_renamed(
                    novel_id=novel_id,
                    entity_id=entity_id,
                    old_name=old_name,
                    new_name=new_name,
                )
            except Exception:
                logger.warning(
                    "kb_lifecycle_observer_failed",
                    change="renamed",
                    consumer_feature=getattr(observer, "consumer_feature", "?"),
                    entity_id=str(entity_id),
                    exc_info=True,
                )

    async def notify_deprecated(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
    ) -> None:
        """Notify every observer that a KB entity became ``deprecated``."""
        for observer in self._observers:
            try:
                await observer.on_kb_entity_deprecated(
                    novel_id=novel_id,
                    entity_id=entity_id,
                )
            except Exception:
                logger.warning(
                    "kb_lifecycle_observer_failed",
                    change="deprecated",
                    consumer_feature=getattr(observer, "consumer_feature", "?"),
                    entity_id=str(entity_id),
                    exc_info=True,
                )

    async def notify_deleted(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
    ) -> None:
        """Notify every observer that a KB entity was hard-deleted.

        Hard delete is destructive and stays hard delete (ADR-050:
        no tombstone column on ``KBEntry``). Observers decide whether
        to emit a ``RefIntegrityIssue(reason="deleted_ref_without_tombstone")``
        or maintain their own tombstone marker.
        """
        for observer in self._observers:
            try:
                await observer.on_kb_entity_deleted(
                    novel_id=novel_id,
                    entity_id=entity_id,
                )
            except Exception:
                logger.warning(
                    "kb_lifecycle_observer_failed",
                    change="deleted",
                    consumer_feature=getattr(observer, "consumer_feature", "?"),
                    entity_id=str(entity_id),
                    exc_info=True,
                )
