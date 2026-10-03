"""Integration tests for the bulk extraction job API (F2, ADR-092 §4).

Real endpoints over the REAL ``BulkExtractionService`` + REAL in-memory
registry store — only the dispatcher is overridden (a recording no-op) so
tests drive job state via ``registry.mark_*`` without launching the AI
runner (the plan's prescribed bypass through the DI seam).

Covers the spec §4 wire shapes (201 start / status poll / results /
cancel / resume), the validation rules of §4.6 (ownership gate 404,
unknown chapter 422, single active job 409, foreign ≡ unknown job 404),
and the T3-review riders: the novel-job binding hardening (a job of one
of the user's OWN novels operated under the other novel's URL → 404) and
the drain registration (pinned in the runner unit tests).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.kb.bulk_extraction import registry
from tests.integration.kb._bulk_extraction_helpers import (
    NoopDispatcher,
    add_chapters,
    create_novel,
    output,
    register_user,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

#: The bulk registry is process-global — sweep it around every test here
#: (fixtures: bulk_dispatcher / bulk_novel_id / bulk_chapter_ids in conftest).
pytestmark = pytest.mark.usefixtures("clean_bulk_registry")


# ---------------------------------------------------------------------------
# Start (spec §4.1)
# ---------------------------------------------------------------------------


class TestStartBulkExtraction:
    async def test_start_returns_201_with_job_view_no_chapter_echo(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_chapter_ids: list[UUID],
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        resp = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(cid) for cid in bulk_chapter_ids]},
            headers=auth_headers,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["novel_id"] == str(bulk_novel_id)
        assert body["status"] == "pending"
        assert body["totals"] == {"total": 3, "done": 0, "failed": 0, "remaining": 3}
        assert body["error"] is None
        assert "chapters" not in body  # the start response does not echo the list
        assert len(bulk_dispatcher.dispatched) == 1  # the runner was dispatched
        assert bulk_dispatcher.dispatched[0][1] == bulk_novel_id

    async def test_status_lists_chapters_in_position_order_as_pending(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_chapter_ids: list[UUID],
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        requested = [
            bulk_chapter_ids[2],
            bulk_chapter_ids[0],
            bulk_chapter_ids[1],
        ]  # request order ≠ position
        start = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(cid) for cid in requested]},
            headers=auth_headers,
        )
        job_id = start.json()["job_id"]

        resp = await client.get(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/status",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert [row["chapter_id"] for row in body["chapters"]] == [
            str(cid) for cid in bulk_chapter_ids
        ]
        assert [row["position"] for row in body["chapters"]] == [0, 1, 2]
        assert all(row["state"] == "pending" for row in body["chapters"])
        assert all(row["item_count"] is None for row in body["chapters"])

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

    async def test_start_on_foreign_novel_is_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        foreign_headers = await register_user(client)

        resp = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(uuid4())]},
            headers=foreign_headers,
        )

        assert resp.status_code == 404

    async def test_second_active_job_for_the_novel_conflicts_409(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_chapter_ids: list[UUID],
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        payload = {"chapter_ids": [str(cid) for cid in bulk_chapter_ids[:2]]}
        first = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk", json=payload, headers=auth_headers
        )
        assert first.status_code == 201

        second = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk", json=payload, headers=auth_headers
        )

        assert second.status_code == 409

    async def test_start_without_auth_is_401(
        self, client: AsyncClient, bulk_novel_id: UUID
    ) -> None:
        resp = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(uuid4())]},
        )

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Results (spec §4.3) — outputs present iff done
# ---------------------------------------------------------------------------


class TestBulkResults:
    async def test_results_carry_outputs_only_for_done_chapters(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_chapter_ids: list[UUID],
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        start = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(cid) for cid in bulk_chapter_ids]},
            headers=auth_headers,
        )
        job_id = start.json()["job_id"]
        # Drive two chapters to done in-process (the runner is bypassed).
        registry.mark_chapter_done(job_id, bulk_chapter_ids[0], output(2))
        registry.mark_chapter_done(job_id, bulk_chapter_ids[1], output(0))

        results = await client.get(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/results",
            headers=auth_headers,
        )
        status = await client.get(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/status",
            headers=auth_headers,
        )

        assert results.status_code == 200
        body = results.json()
        # The no-op dispatcher never ran the loop, so the job is still PENDING
        # (results stay readable in any job state — spec §4.3).
        assert body["status"] == "pending"
        outputs = [row["output"] for row in body["chapters"]]
        assert (outputs[0] is not None) and (len(outputs[0]["results"]) == 2)
        assert (outputs[1] is not None) and (outputs[1]["results"] == [])
        assert outputs[2] is None
        counts = [row["item_count"] for row in status.json()["chapters"]]
        assert counts == [2, 0, None]

    async def test_results_of_unknown_job_are_404(
        self, client: AsyncClient, auth_headers: dict[str, str], bulk_novel_id: UUID
    ) -> None:
        resp = await client.get(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{uuid4().hex}/results",
            headers=auth_headers,
        )

        assert resp.status_code == 404

    async def test_results_of_foreign_user_are_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_chapter_ids: list[UUID],
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        start = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(cid) for cid in bulk_chapter_ids]},
            headers=auth_headers,
        )
        job_id = start.json()["job_id"]
        foreign_headers = await register_user(client)

        resp = await client.get(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/results",
            headers=foreign_headers,
        )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cancel + resume (spec §4.4/§4.5)
# ---------------------------------------------------------------------------


class TestCancelAndResume:
    async def test_cancel_conflict_on_terminal_then_resume_keeps_done(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_chapter_ids: list[UUID],
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        start = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(cid) for cid in bulk_chapter_ids]},
            headers=auth_headers,
        )
        job_id = start.json()["job_id"]
        registry.mark_chapter_done(job_id, bulk_chapter_ids[0], output(1))

        cancel = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/cancel",
            headers=auth_headers,
        )
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancelling"

        # The runner honors the flag between chapters → terminal CANCELLED.
        registry.mark_cancelled(job_id, "cancelled by user")

        cancel_again = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/cancel",
            headers=auth_headers,
        )
        assert cancel_again.status_code == 409

        resume = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/resume",
            headers=auth_headers,
        )
        assert resume.status_code == 200
        assert resume.json()["status"] == "pending"
        assert resume.json()["error"] is None

        status = await client.get(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/status",
            headers=auth_headers,
        )
        rows = status.json()["chapters"]
        assert rows[0]["state"] == "done"  # done baseline kept (resume §4.5)
        assert rows[0]["item_count"] == 1
        assert all(row["state"] == "pending" for row in rows[1:])
        assert len(bulk_dispatcher.dispatched) == 2  # resume re-dispatched the runner

    async def test_resume_of_completed_job_conflicts_409(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_chapter_ids: list[UUID],
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        start = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk",
            json={"chapter_ids": [str(cid) for cid in bulk_chapter_ids]},
            headers=auth_headers,
        )
        job_id = start.json()["job_id"]
        for cid in bulk_chapter_ids:
            registry.mark_chapter_done(job_id, cid, output(1))
        registry.mark_job_completed(job_id)

        resp = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/resume",
            headers=auth_headers,
        )

        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Novel-job binding (T3-review rider) — own novels A+B, B's job under A's URL
# ---------------------------------------------------------------------------


class TestNovelJobBinding:
    async def test_own_job_of_another_novel_under_this_novels_url_is_404(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        bulk_novel_id: UUID,
        bulk_chapter_ids: list[UUID],
        db_session: AsyncSession,
        bulk_dispatcher: NoopDispatcher,
    ) -> None:
        other_novel = await create_novel(client, auth_headers, "Other Novel")
        other_chapters = await add_chapters(db_session, other_novel, count=1)
        start = await client.post(
            f"/api/v1/novels/{other_novel}/kb/extract/bulk",
            json={"chapter_ids": [str(cid) for cid in other_chapters]},
            headers=auth_headers,
        )
        job_id = start.json()["job_id"]

        status = await client.get(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/status",
            headers=auth_headers,
        )
        results = await client.get(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/results",
            headers=auth_headers,
        )
        cancel = await client.post(
            f"/api/v1/novels/{bulk_novel_id}/kb/extract/bulk/{job_id}/cancel",
            headers=auth_headers,
        )

        assert status.status_code == 404
        assert results.status_code == 404
        assert cancel.status_code == 404
        # Reads are pure: no mutation happened before the binding check. The
        # cancel's store write precedes the check (the rider's check-after-
        # read pattern), so the flag flip lands on the user's OWN job under
        # its correct URL — self-inflicted, never cross-user (the store's
        # owner pinning runs first).
        intact = await client.get(
            f"/api/v1/novels/{other_novel}/kb/extract/bulk/{job_id}/status",
            headers=auth_headers,
        )
        assert intact.status_code == 200
        assert intact.json()["status"] == "cancelling"
