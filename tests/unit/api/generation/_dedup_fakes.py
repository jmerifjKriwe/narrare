from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol


class _FakeKBEntry:
    def __init__(self, name: str, entity_type: str = "character") -> None:
        self.name = name
        self.entity_type = entity_type


class _FakeKBRepository:
    def __init__(self, entries: list[_FakeKBEntry] | None = None) -> None:
        self._entries = entries or []

    async def list_entries(
        self,
        novel_id: uuid.UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[_FakeKBEntry], int]:
        filtered = self._entries
        if entity_type is not None:
            filtered = [e for e in filtered if e.entity_type == entity_type]
        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], total

    async def create(self, entry: Any) -> Any:
        raise NotImplementedError("stub")

    async def get_by_id(self, entry_id: uuid.UUID) -> Any:
        raise NotImplementedError("stub")

    async def get_by_slug(self, novel_id: uuid.UUID, slug: str) -> Any:
        raise NotImplementedError("stub")

    async def get_by_name(self, novel_id: uuid.UUID, name: str) -> Any:
        raise NotImplementedError("stub")

    async def search_by_name_prefix(
        self,
        novel_id: uuid.UUID,
        prefix: str,
        limit: int = 10,
    ) -> list[Any]:
        raise NotImplementedError("stub")

    async def update(self, entry: Any, data: dict[str, object]) -> Any:
        raise NotImplementedError("stub")

    async def delete(self, entry: Any) -> None:
        raise NotImplementedError("stub")

    async def search(
        self,
        novel_id: uuid.UUID,
        query: str,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Any], int]:
        raise NotImplementedError("stub")

    async def count_by_novel(self, novel_id: uuid.UUID) -> int:
        raise NotImplementedError("stub")


def kb_repo(entries: list[_FakeKBEntry]) -> KBRepositoryProtocol:
    return cast("KBRepositoryProtocol", _FakeKBRepository(entries))


def json_names(names: list[dict[str, str]]) -> str:
    return json.dumps(names)
