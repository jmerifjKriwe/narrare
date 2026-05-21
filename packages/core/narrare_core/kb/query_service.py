"""KB Query Service — Protocol für Agent-zugängliche KB-Operationen.

Dieses Protocol wird von KBAgent genutzt und stellt eine vereinfachte,
agent-freundliche Schnittstelle zum KB-System dar.

Die Implementierung (im Backend) wrapped das bestehende
KBRepositoryProtocol + RelationshipRepositoryProtocol.

Siehe ADR-015 Phase 3.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class KBQueryService(Protocol):
    """Agent-freundliche KB-Query-Schnittstelle.

    Vereinfacht die bestehenden Repository/Service-Protocols
    für die Nutzung durch KBAgent-Tools. Novel- und User-IDs
    werden vom Adapter vorausgefüllt.
    """

    async def search(
        self,
        query: str,
        *,
        entity_type: str | None = None,
    ) -> list[object]: ...

    async def get_by_name(self, name: str) -> object | None: ...

    async def get_related(
        self,
        entity_id: object,
        *,
        relation_type: str | None = None,
    ) -> list[object]: ...
