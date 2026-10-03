"""Start-path validation matrix for the bulk extraction API (ADR-092 §4.6).

The 422 surface of ``POST …/kb/extract/bulk``: unknown/foreign chapter ids,
duplicates, and the engine cap — every rejection names the offending id
(where one exists). Split from ``test_bulk_extraction_api.py`` solely for
the RULE-04 400-line limit; same fixtures (conftest), same DI bypass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.kb.bulk_extraction.contracts import BULK_EXTRACT_MAX_CHAPTERS

if TYPE_CHECKING:
    from uuid import UUID

    from httpx import AsyncClient

    from tests.integration.kb._bulk_extraction_helpers import NoopDispatcher


class TestStartValidation:
    """§4.6 rule 1-2: duplicates and unknown ids → 422 naming the id; cap → 422."""

    async def test_start_with_unknown_chapter_id_is_422_naming_it(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_chapter_ids: list[UUID],
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        unknown = uuid4()

        resp = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(bulk_chapter_ids[0]), str(unknown)]},
            headers=auth_headers,
        )

        assert resp.status_code == 422
        assert str(unknown) in resp.json()["detail"]

    async def test_start_with_duplicate_chapter_ids_is_422_naming_it(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_chapter_ids: list[UUID],
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        duplicate = bulk_chapter_ids[0]

        resp = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(duplicate), str(duplicate)]},
            headers=auth_headers,
        )

        assert resp.status_code == 422
        assert str(duplicate) in resp.json()["detail"]

    async def test_start_over_the_engine_cap_is_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        resp = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(uuid4()) for _ in range(BULK_EXTRACT_MAX_CHAPTERS + 1)]},
            headers=auth_headers,
        )

        assert resp.status_code == 422
