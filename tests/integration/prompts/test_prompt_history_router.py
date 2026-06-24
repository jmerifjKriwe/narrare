"""CR-AUFG-07-19 — Prompt History router integration tests.

Exercises the four history endpoints plus the PUT-save-records-history
redirect against the real app (real service, real repo, test DB session).
Each test resets the override first so cross-test file state does not leak
into ``is_active`` derivation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

_HISTORY_CONTENT_A = "---\nprompt_version: '1.0.0'\n---\n\nOverride content A."
_HISTORY_CONTENT_B = "---\nprompt_version: '1.0.0'\n---\n\nOverride content B (longer)."


@pytest.fixture
async def prompt_id(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    """Resolve a real bundled prompt id, skipping when none are bundled."""
    list_resp = await client.get("/api/v1/prompts", headers=auth_headers)
    prompts = list_resp.json()
    if not prompts:
        pytest.skip("No prompts available in bundled directory")
    return prompts[0]["prompt_id"]


async def _reset(client: AsyncClient, auth_headers: dict[str, str], pid: str) -> None:
    await client.delete(f"/api/v1/prompts/{pid}/override", headers=auth_headers)


class TestHistoryList:
    async def test_list_returns_200_with_contract_shape(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        prompt_id: str,
    ) -> None:
        """GET /history returns 200 with the list response contract."""
        await _reset(client, auth_headers, prompt_id)
        response = await client.get(
            f"/api/v1/prompts/{prompt_id}/history",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        for key in ("prompt_id", "scope", "total", "limit", "offset", "revisions"):
            assert key in data
        assert data["prompt_id"] == prompt_id
        assert data["scope"] == "project"
        assert isinstance(data["revisions"], list)

    async def test_list_without_auth_returns_401(self, client: AsyncClient, prompt_id: str) -> None:
        response = await client.get(f"/api/v1/prompts/{prompt_id}/history")
        assert response.status_code == 401


class TestSaveRecordsHistory:
    async def test_put_save_records_a_revision(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        prompt_id: str,
    ) -> None:
        """PUT /prompts/{id} (redirected) records a history revision."""
        await _reset(client, auth_headers, prompt_id)

        save_resp = await client.put(
            f"/api/v1/prompts/{prompt_id}",
            json={"content": _HISTORY_CONTENT_A, "change_reason": "initial"},
            headers=auth_headers,
        )
        assert save_resp.status_code == 204

        hist_resp = await client.get(
            f"/api/v1/prompts/{prompt_id}/history",
            headers=auth_headers,
        )
        assert hist_resp.status_code == 200
        data = hist_resp.json()
        assert data["total"] >= 1
        latest = data["revisions"][0]
        assert latest["source"] == "save"
        assert latest["change_reason"] == "initial"
        assert latest["is_active"] is True


class TestCompare:
    async def test_compare_active_vs_revision_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        prompt_id: str,
    ) -> None:
        """GET /history/compare?from={rev}&to=active returns from/to content."""
        await _reset(client, auth_headers, prompt_id)
        await client.put(
            f"/api/v1/prompts/{prompt_id}",
            json={"content": _HISTORY_CONTENT_A},
            headers=auth_headers,
        )
        await client.put(
            f"/api/v1/prompts/{prompt_id}",
            json={"content": _HISTORY_CONTENT_B},
            headers=auth_headers,
        )

        hist = (
            await client.get(f"/api/v1/prompts/{prompt_id}/history", headers=auth_headers)
        ).json()
        # Select the older revision by content rather than list position: within
        # a single test transaction every revision shares the same created_at
        # (PostgreSQL now() = transaction start), so list order is not a stable
        # insertion proxy here. (Production saves are one-per-transaction, so
        # created_at is unique and ordering is deterministic.)
        oldest_id = next(
            r["id"] for r in hist["revisions"] if "Override content A." in r["content"]
        )

        resp = await client.get(
            f"/api/v1/prompts/{prompt_id}/history/compare",
            params={"from": oldest_id, "to": "active"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["from_id"] == oldest_id
        assert data["to_id"] == "active"
        assert data["to_source"] == "active"
        assert "Override content A." in data["from_content"]
        assert "Override content B" in data["to_content"]


class TestRestore:
    async def test_restore_round_trip(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        prompt_id: str,
    ) -> None:
        """POST /history/{rev}/restore writes the file + records a new revision."""
        await _reset(client, auth_headers, prompt_id)
        await client.put(
            f"/api/v1/prompts/{prompt_id}",
            json={"content": _HISTORY_CONTENT_A},
            headers=auth_headers,
        )
        await client.put(
            f"/api/v1/prompts/{prompt_id}",
            json={"content": _HISTORY_CONTENT_B},
            headers=auth_headers,
        )

        hist = (
            await client.get(f"/api/v1/prompts/{prompt_id}/history", headers=auth_headers)
        ).json()
        # Select the revision to restore by content (see compare test note on
        # within-transaction created_at ties).
        oldest_id = next(
            r["id"] for r in hist["revisions"] if "Override content A." in r["content"]
        )
        total_before = hist["total"]

        resp = await client.post(
            f"/api/v1/prompts/{prompt_id}/history/{oldest_id}/restore",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["restored_revision"]["source"] == "restore"
        assert data["restored_revision"]["restored_from_id"] == oldest_id
        assert data["restored_revision"]["is_active"] is True
        assert "Override content A." in data["active_content"]

        # A new revision was appended.
        hist_after = (
            await client.get(f"/api/v1/prompts/{prompt_id}/history", headers=auth_headers)
        ).json()
        assert hist_after["total"] == total_before + 1
        assert any(r["source"] == "restore" for r in hist_after["revisions"])

    async def test_restore_unknown_revision_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        prompt_id: str,
    ) -> None:
        import uuid

        resp = await client.post(
            f"/api/v1/prompts/{prompt_id}/history/{uuid.uuid4()}/restore",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestClear:
    async def test_clear_deletes_history_and_keeps_override(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        prompt_id: str,
    ) -> None:
        """DELETE /history removes revisions; the active override remains."""
        await _reset(client, auth_headers, prompt_id)
        await client.put(
            f"/api/v1/prompts/{prompt_id}",
            json={"content": _HISTORY_CONTENT_A},
            headers=auth_headers,
        )
        before = (
            await client.get(f"/api/v1/prompts/{prompt_id}/history", headers=auth_headers)
        ).json()
        assert before["total"] >= 1

        resp = await client.delete(
            f"/api/v1/prompts/{prompt_id}/history",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] >= 1

        after = (
            await client.get(f"/api/v1/prompts/{prompt_id}/history", headers=auth_headers)
        ).json()
        assert after["total"] == 0

        # The active override file is untouched — GET prompt still overridden.
        detail = (await client.get(f"/api/v1/prompts/{prompt_id}", headers=auth_headers)).json()
        assert detail["is_overridden"] is True

    async def test_clear_without_auth_returns_401(
        self, client: AsyncClient, prompt_id: str
    ) -> None:
        resp = await client.delete(f"/api/v1/prompts/{prompt_id}/history")
        assert resp.status_code == 401
