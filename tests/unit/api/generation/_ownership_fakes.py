"""Shared fakes for generation ownership tests (IDOR remediation S12b).

``RecordingNovelRepo`` models real novel ownership for the Pattern B gate;
``permissive_novel_repo`` owns everything so NON-ownership tests stay
independent of the gate (they generate random project ids).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class RecordingNovelRepo:
    """Fake NovelRepositoryProtocol with a real ownership map.

    Permissive by default (owns everything); pass an explicit ``ownership``
    map ``{novel_id: user_id}`` to model real ownership (S12b matrix).
    """

    def __init__(self, ownership: dict[UUID, UUID] | None = None) -> None:
        self._ownership = ownership
        self.get_by_id_calls: list[tuple[UUID, UUID]] = []

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> object | None:
        self.get_by_id_calls.append((novel_id, user_id))
        if self._ownership is None or self._ownership.get(novel_id) == user_id:
            return object()  # the gate only checks existence
        return None


def permissive_novel_repo() -> RecordingNovelRepo:
    """Novel repo that owns everything (keeps non-ownership tests green)."""
    return RecordingNovelRepo()
