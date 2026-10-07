# tests/unit/api/analytics/test_costs_export.py
"""Unit tests for the STATS-002 CSV export slice (spec B-1..B-5).

Service + router coverage lives here (slice budget: ≤3 source files + test
files); the ``UsageRecordRepository.stream_month`` query-shape tests live in
``test_usage_record_repository.py`` (their natural home — kept there to stay
under the RULE-04 test-file limit).

- ``CostQueryService.export_csv_lines`` / ``export_csv_headers`` — real
  service over a fake repository: BOM+header first line, exact column order,
  empty cells for NULL cost/novel, ISO-8601 UTC timestamps, LAZY row pulls.
- ``GET /analytics/costs/export`` — router harness mirrored from
  ``test_costs_router.py`` (minimal app + overrides + 422 handler):
  200/content-type/disposition, user scoping, 422 malformed + year-edge,
  401, streaming shape (headers precede any row pull; body starts with the
  header line).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import UUID

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from narrare._app.dependencies import get_current_user_id
from narrare.analytics.dependencies import get_cost_query_service
from narrare.analytics.models import UsageRecordRow
from narrare.analytics.router import invalid_month_error_handler, router
from narrare.analytics.service import CostQueryService, InvalidMonthError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from narrare.analytics.repository import UsageRecordRepository

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"
NOVEL_ID = UUID("11111111-1111-1111-1111-111111111111")

_JAN_START = datetime(2026, 1, 1, tzinfo=UTC)
_FEB_START = datetime(2026, 2, 1, tzinfo=UTC)

# Spec B-3 — exact header row, pinned literally (not via the csv module, so
# a service regression cannot make the test re-implement itself green).
BOM = "\ufeff"  # UTF-8 byte-order mark (spec B-2: Excel-compatible)
HEADER_LINE = (
    "created_at,intent,provider,model_id,tokens_in,tokens_out,"
    "cache_read_tokens,cache_creation_tokens,duration_ms,cost_usd,novel_id\r\n"
)

# Expected data lines, hand-built from the seed rows below (spec B-3: empty
# cell for NULL cost/novel, int token/duration cells, ISO-8601 UTC stamp).
_ROW_PRICED = (
    f"2026-01-10T12:30:00+00:00,summarize,anthropic,claude-haiku,10,20,5,7,500,0.003,{NOVEL_ID}\r\n"
)
_ROW_UNPRICED = "2026-01-11T08:00:00+00:00,write,openai,gpt-x,50,60,0,0,1200,,\r\n"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeStreamRepository:
    """Preset rows + ``stream_month`` call recording (real service, no SQL).

    ``rows_pulled`` counts how many rows the consumer has actually drawn —
    the lazy-streaming assertion (spec B-4: no full-month list in memory).
    """

    def __init__(self, rows: Sequence[UsageRecordRow]) -> None:
        self._rows = list(rows)
        self.calls: list[tuple[UUID, datetime, datetime]] = []
        self.rows_pulled = 0

    async def stream_month(
        self, user_id: UUID, start: datetime, end: datetime
    ) -> AsyncIterator[UsageRecordRow]:
        self.calls.append((user_id, start, end))
        for row in self._rows:
            self.rows_pulled += 1
            yield row


def _usage_row(**overrides: object) -> UsageRecordRow:
    defaults: dict[str, object] = {
        "user_id": UUID(TEST_USER_ID),
        "intent": "summarize",
        "provider": "anthropic",
        "model_id": "claude-haiku",
        "tokens_in": 10,
        "tokens_out": 20,
        "cache_read_tokens": 5,
        "cache_creation_tokens": 7,
        "duration_ms": 500,
        "cost_usd": Decimal("0.003"),
        "created_at": datetime(2026, 1, 10, 12, 30, tzinfo=UTC),
    }
    defaults.update(overrides)
    return UsageRecordRow(**defaults)  # pyright: ignore[reportArgAssignType]


def _seed_rows() -> list[UsageRecordRow]:
    """Two rows in created_at order: priced+novel first, unpriced+no-novel second."""
    return [
        _usage_row(novel_id=NOVEL_ID),
        _usage_row(
            intent="write",
            provider="openai",
            model_id="gpt-x",
            tokens_in=50,
            tokens_out=60,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            duration_ms=1200,
            cost_usd=None,
            created_at=datetime(2026, 1, 11, 8, 0, tzinfo=UTC),
        ),
    ]


def _service(repo: _FakeStreamRepository) -> CostQueryService:
    return CostQueryService(cast("UsageRecordRepository", repo))


def _make_app(repo: _FakeStreamRepository, *, authenticate: bool = True) -> FastAPI:
    """Minimal app: analytics router + auth/service overrides + 422 handler."""
    app = FastAPI()
    app.include_router(router)
    app.exception_handler(InvalidMonthError)(invalid_month_error_handler)
    if authenticate:
        app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_cost_query_service] = lambda: _service(repo)
    return app


@asynccontextmanager
async def _client(app: ASGIApp) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Service — export_csv_lines / export_csv_headers
# ---------------------------------------------------------------------------


class TestExportCsvLines:
    async def test_export_lines_yields_bom_header_then_rows_lazily(self) -> None:
        """First line = BOM+header (no row pulled yet); rows pulled on demand."""
        repo = _FakeStreamRepository(_seed_rows())
        generator = _service(repo).export_csv_lines(UUID(TEST_USER_ID), "2026-01")

        first = await generator.__anext__()
        assert first == BOM + HEADER_LINE
        assert repo.rows_pulled == 0  # header alone — zero rows in memory

        second = await generator.__anext__()
        assert second == _ROW_PRICED
        assert repo.rows_pulled == 1  # pulled only when the line was needed

    async def test_export_lines_formats_unpriced_and_novelless_rows(self) -> None:
        """NULL cost → empty cell; NULL novel → empty cell; ints verbatim."""
        repo = _FakeStreamRepository(_seed_rows())

        lines = [
            line async for line in _service(repo).export_csv_lines(UUID(TEST_USER_ID), "2026-01")
        ]

        assert lines == [BOM + HEADER_LINE, _ROW_PRICED, _ROW_UNPRICED]

    async def test_export_lines_empty_month_yields_only_header(self) -> None:
        """A month without usage still yields a parseable (header-only) CSV."""
        repo = _FakeStreamRepository([])

        lines = [
            line async for line in _service(repo).export_csv_lines(UUID(TEST_USER_ID), "2026-01")
        ]

        assert lines == [BOM + HEADER_LINE]

    async def test_export_lines_streams_the_month_window_for_the_caller(
        self,
    ) -> None:
        """Repository window: user-scoped, UTC [first-of-month, next-month)."""
        repo = _FakeStreamRepository([])

        async for _ in _service(repo).export_csv_lines(UUID(TEST_USER_ID), "2026-01"):
            pass

        assert repo.calls == [(UUID(TEST_USER_ID), _JAN_START, _FEB_START)]

    @pytest.mark.parametrize("bad_month", ["garbage", "0000-01", "9999-12"])
    async def test_export_lines_invalid_month_raises_before_streaming(self, bad_month: str) -> None:
        """Invalid/regex-valid-but-unconstructible months never touch the repo."""
        repo = _FakeStreamRepository(_seed_rows())

        with pytest.raises(InvalidMonthError):
            async for _ in _service(repo).export_csv_lines(UUID(TEST_USER_ID), bad_month):
                pass

        assert repo.calls == []


class TestExportCsvHeaders:
    async def test_headers_contain_disposition_for_explicit_month(self) -> None:
        repo = _FakeStreamRepository([])

        headers = _service(repo).export_csv_headers("2026-01")

        assert headers == {
            "Content-Disposition": 'attachment; filename="narrare-costs-2026-01.csv"'
        }

    async def test_headers_resolve_the_current_month_when_omitted(self) -> None:
        """``month=None`` → filename carries the current server-local month."""
        repo = _FakeStreamRepository([])
        label_before = datetime.now().astimezone().strftime("%Y-%m")

        headers = _service(repo).export_csv_headers(None)

        label_after = datetime.now().astimezone().strftime("%Y-%m")
        candidates = {
            f'attachment; filename="narrare-costs-{label}.csv"'
            for label in (label_before, label_after)
        }
        assert headers["Content-Disposition"] in candidates

    @pytest.mark.parametrize("bad_month", ["2026-13", "0000-01", "9999-12"])
    async def test_headers_reject_invalid_months_eagerly(self, bad_month: str) -> None:
        """Eager validation → InvalidMonthError BEFORE any stream starts."""
        repo = _FakeStreamRepository([])

        with pytest.raises(InvalidMonthError):
            _service(repo).export_csv_headers(bad_month)

        assert repo.calls == []


# ---------------------------------------------------------------------------
# Router — GET /analytics/costs/export
# ---------------------------------------------------------------------------


class TestExportRoute:
    async def test_export_returns_200_with_csv_headers_and_exact_body(
        self,
    ) -> None:
        """200, ``text/csv; charset=utf-8``, disposition, BOM+header+rows."""
        repo = _FakeStreamRepository(_seed_rows())

        async with _client(_make_app(repo)) as ac:
            response = await ac.get("/analytics/costs/export", params={"month": "2026-01"})

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert (
            response.headers["content-disposition"]
            == 'attachment; filename="narrare-costs-2026-01.csv"'
        )
        assert response.text == BOM + HEADER_LINE + _ROW_PRICED + _ROW_UNPRICED

    async def test_export_without_month_resolves_current_month_in_filename(
        self,
    ) -> None:
        """Omitted month → filename carries the current server-local month."""
        repo = _FakeStreamRepository([])
        label_before = datetime.now().astimezone().strftime("%Y-%m")

        async with _client(_make_app(repo)) as ac:
            response = await ac.get("/analytics/costs/export")

        label_after = datetime.now().astimezone().strftime("%Y-%m")
        candidates = {
            f'attachment; filename="narrare-costs-{label}.csv"'
            for label in (label_before, label_after)
        }
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-disposition"] in candidates
        assert len(repo.calls) == 1  # a stream was opened for that month

    async def test_export_scopes_to_the_authenticated_user_and_month_window(
        self,
    ) -> None:
        """Auth id (JWT ``sub``) scopes the stream; window is [Jan 1, Feb 1)."""
        repo = _FakeStreamRepository([])

        async with _client(_make_app(repo)) as ac:
            await ac.get("/analytics/costs/export", params={"month": "2026-01"})

        assert repo.calls == [(UUID(TEST_USER_ID), _JAN_START, _FEB_START)]

    @pytest.mark.parametrize("bad_month", ["2026-13", "garbage"])
    async def test_export_with_malformed_month_returns_422(self, bad_month: str) -> None:
        """FastAPI Query pattern rejects malformed months before the service."""
        repo = _FakeStreamRepository([])

        async with _client(_make_app(repo)) as ac:
            response = await ac.get("/analytics/costs/export", params={"month": bad_month})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert repo.calls == []

    @pytest.mark.parametrize("edge_month", ["0000-01", "9999-12"])
    async def test_export_with_unconstructible_year_returns_422_not_500(
        self, edge_month: str
    ) -> None:
        """Regex-valid year-edge months → 422 via the registered handler."""
        repo = _FakeStreamRepository([])

        async with _client(_make_app(repo)) as ac:
            response = await ac.get("/analytics/costs/export", params={"month": edge_month})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert edge_month in response.json()["detail"]
        assert repo.calls == []

    async def test_export_without_token_returns_401(self) -> None:
        """401 unauthenticated; the service is never called."""
        repo = _FakeStreamRepository([])

        async with _client(_make_app(repo, authenticate=False)) as ac:
            response = await ac.get("/analytics/costs/export")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers["www-authenticate"] == "Bearer"
        assert repo.calls == []

    async def test_export_first_chunk_is_the_bom_header_line(self) -> None:
        """Streaming shape: response headers are sent before ANY data row is
        pulled (lazy start pinned at the router boundary) and the body starts
        with the BOM+header line (spec B-2/B-4).

        httpx 0.28 ``ASGITransport`` runs the app to completion (it buffers the
        full body) before the client sees the response, so the laziness pin
        snapshots ``rows_pulled`` when the ASGI ``http.response.start`` message
        passes through instead of checking inside the stream context.
        """
        repo = _FakeStreamRepository(_seed_rows())
        rows_at_response_start: list[int] = []

        def with_rows_snapshot(inner: ASGIApp) -> ASGIApp:
            async def app(scope: Scope, receive: Receive, send: Send) -> None:
                async def send_wrapper(message: Message) -> None:
                    if message["type"] == "http.response.start":
                        rows_at_response_start.append(repo.rows_pulled)
                    await send(message)

                await inner(scope, receive, send_wrapper)

            return app

        async with (
            _client(with_rows_snapshot(_make_app(repo))) as ac,
            ac.stream("GET", "/analytics/costs/export", params={"month": "2026-01"}) as response,
        ):
            assert response.status_code == status.HTTP_200_OK

            await response.aread()

            assert rows_at_response_start == [0]  # headers flew; zero rows pulled
            assert response.text.startswith(BOM + HEADER_LINE)
