"""Integration tests for split/merge ops over HTTP (F1, ADR-091 Am. 2).

Verifies the deployed v2 wire contract end-to-end: preview enrichment
(``split_candidates``, .md-gated), commit applying ``splits``/``merges``
(ORIGINAL space) alongside ``excluded_indices``/``title_overrides``
(FINAL space), per-op drift rejections (422 naming the offending op),
and ``extra="forbid"`` strictness on the adjustments form field.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.novels.models import Novel
from tests.integration._helpers import extract_user_id

if TYPE_CHECKING:
    import uuid

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _create_novel(db_session: AsyncSession, user_id: uuid.UUID) -> Novel:
    novel = Novel(user_id=user_id, title="F1 Target")
    db_session.add(novel)
    await db_session.flush()
    return novel


def _files() -> list[tuple[str, tuple[str, bytes, str]]]:
    """long.md carries two ``###`` subheadings (2 split candidates)."""
    return [
        (
            "files",
            (
                "long.md",
                b"# The Long Chapter\nalpha beta\n### Scene A\ngamma\n### Scene B\ndelta epsilon",
                "text/markdown",
            ),
        ),
        ("files", ("next.md", b"# After\nquiet morning", "text/markdown")),
    ]


class TestPreviewEnrichment:
    async def test_preview_returns_split_candidates(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post("/api/v1/import/preview", headers=auth_headers, files=_files())
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["split_candidates"] == [
            {"ordinal": 0, "heading": "Scene A", "words_before": 2},
            {"ordinal": 1, "heading": "Scene B", "words_before": 6},
        ]
        assert response.json()["items"][1]["split_candidates"] == []

    async def test_preview_txt_has_empty_candidates(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/import/preview",
            headers=auth_headers,
            files=[("files", ("notes.txt", b"Chapter 1\nc1 words", "text/plain"))],
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["split_candidates"] == []


class TestCommitWithOperations:
    async def test_split_merge_exclude_rename_persists_expected_rows(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel = await _create_novel(db_session, extract_user_id(auth_headers))
        adjustments = (
            '{"splits": [{"index": 0, "at": [1]}], "merges": [], '
            '"excluded_indices": [1], "title_overrides": {"0": "Kept Intro"}}'
        )
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": adjustments},
            files=_files(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["created_count"] == 2
        assert [c["title"] for c in body["chapters"]] == ["Kept Intro", "After"]

        chapters = await client.get(f"/api/v1/novels/{novel.id}/chapters", headers=auth_headers)
        assert [c["title"] for c in chapters.json()] == ["Kept Intro", "After"]

    async def test_cross_file_merge_first_constituent_wins(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel = await _create_novel(db_session, extract_user_id(auth_headers))
        files = [
            ("files", ("a.md", b"# Storm\nwind and rain", "text/markdown")),
            ("files", ("b.md", b"# After\nquiet morning", "text/markdown")),
        ]
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"merges": [{"indices": [0, 1]}]}'},
            files=files,
        )
        assert response.status_code == 200
        assert response.json()["created_count"] == 1
        chapters = await client.get(f"/api/v1/novels/{novel.id}/chapters", headers=auth_headers)
        chapter = chapters.json()[0]
        assert chapter["title"] == "Storm"
        assert chapter["word_count"] == 5  # recomputed from the joined content

    async def test_unsorted_merge_indices_canonicalized_first_constituent_wins(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        # Core canonicalizes a merge's indices (sorted run); the declared
        # order must not change which constituent is "first" ([1, 0] ≡ [0, 1]).
        novel = await _create_novel(db_session, extract_user_id(auth_headers))
        files = [
            ("files", ("a.md", b"# Storm\nwind and rain", "text/markdown")),
            ("files", ("b.md", b"# After\nquiet morning", "text/markdown")),
        ]
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"merges": [{"indices": [1, 0]}]}'},
            files=files,
        )
        assert response.status_code == 200
        assert response.json()["created_count"] == 1
        chapter = response.json()["chapters"][0]
        assert chapter["title"] == "Storm"
        assert chapter["word_count"] == 5


class TestCommitRejections:
    async def test_stale_split_ordinal_422_names_the_op(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel = await _create_novel(db_session, extract_user_id(auth_headers))
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={
                "novel_id": str(novel.id),
                "adjustments": '{"splits": [{"index": 0, "at": [9]}]}',
            },
            files=_files(),
        )
        assert response.status_code == 422
        assert "chapter 0" in response.json()["detail"]

    async def test_non_contiguous_merge_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        # Three chapters so [0, 2] is fully in-range — the contiguity check
        # must be what fires (out-of-range indices are a different error).
        novel = await _create_novel(db_session, extract_user_id(auth_headers))
        files = [
            ("files", ("a.md", b"# One\nfirst body", "text/markdown")),
            ("files", ("b.md", b"# Two\nsecond body", "text/markdown")),
            ("files", ("c.md", b"# Three\nthird body", "text/markdown")),
        ]
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"merges": [{"indices": [0, 2]}]}'},
            files=files,
        )
        assert response.status_code == 422
        assert "not contiguous" in response.json()["detail"]
        # rollback proof: nothing was written
        chapters = await client.get(f"/api/v1/novels/{novel.id}/chapters", headers=auth_headers)
        assert chapters.json() == []

    async def test_unknown_adjustment_field_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        # extra="forbid": version-skew defense — unknown keys are a loud 422.
        novel = await _create_novel(db_session, extract_user_id(auth_headers))
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"split_points": [0]}'},
            files=_files(),
        )
        assert response.status_code == 422

    async def test_v1_style_adjustments_still_commit(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        # Empty op set ⇒ final ≡ original space (v1 identity property).
        novel = await _create_novel(db_session, extract_user_id(auth_headers))
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"excluded_indices": [1]}'},
            files=_files(),
        )
        assert response.status_code == 200
        assert response.json()["created_count"] == 1

    async def test_split_on_txt_source_422_names_md_gate(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        # D2a on BOTH phases: commit must reject what preview cannot offer —
        # .txt chapters are merge-only even when their content has ``###``.
        novel = await _create_novel(db_session, extract_user_id(auth_headers))
        files = [
            (
                "files",
                ("notes.txt", b"Chapter 1\nintro words\n### Scene X\nscene words", "text/plain"),
            ),
        ]
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={
                "novel_id": str(novel.id),
                "adjustments": '{"splits": [{"index": 0, "at": [0]}]}',
            },
            files=files,
        )
        assert response.status_code == 422
        assert "not Markdown" in response.json()["detail"]
