"""Wiring tests — production DI equips content-write services with the recorder.

Fix-round proof for STATS-001 (E3a/E3b): the service suites pin recorder
BEHAVIOUR against fakes; this module pins the WIRING — that the production
dependency chain actually hands a ``SqlWritingStatsRecorder`` to the services
(a service constructed with ``writing_stats_recorder=None`` silently skips
every stats event, so a dropped constructor kwarg would be invisible to the
behaviour suites). Mirrors ``tests/unit/api/test_analytics_wiring.py``:
real seams, no database — the recorder only STORES the standalone session
factory, it never opens one during construction.

1. Real FastAPI ``Depends`` resolution of ``chapters.router._get_service``
   (on a probe app with the request session overridden) yields a
   ``ChapterService`` whose recorder IS the production recorder, bound to
   the module-level standalone session factory (RULE-08).
2. ``get_coauthor_apply_service`` is invoked directly by its router rather
   than through ``Depends`` — direct invocation IS the production call
   path — and likewise yields a recorder-equipped ``CoAuthorApplyService``.
"""

from __future__ import annotations

from typing import Annotated
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from narrare._app.database import get_async_session, get_session_factory
from narrare.analytics.writing_stats_recorder import SqlWritingStatsRecorder
from narrare.chapters.router import _get_service as _get_chapter_service
from narrare.chapters.service import ChapterService
from narrare.writing.coauthor_apply_service import CoAuthorApplyService
from narrare.writing.deps_coauthor import get_coauthor_apply_service


def test_chapters_depends_resolution_equips_production_recorder() -> None:
    """Real Depends resolution hands ``_get_service`` the production recorder."""
    captured: dict[str, ChapterService] = {}
    probe = FastAPI()

    @probe.get("/probe")
    async def probe_endpoint(
        service: Annotated[ChapterService, Depends(_get_chapter_service)],
    ) -> dict[str, bool]:
        captured["service"] = service
        return {"ok": True}

    # Request session is only stored in repositories during factory assembly —
    # a bare AsyncMock stands in; no DB connection is made.
    probe.dependency_overrides[get_async_session] = lambda: AsyncMock()

    response = TestClient(probe).get("/probe")

    assert response.status_code == 200, response.text
    service = captured["service"]
    assert isinstance(service, ChapterService)
    recorder = service._writing_stats_recorder  # pyright: ignore[reportPrivateUsage]
    assert isinstance(recorder, SqlWritingStatsRecorder)
    # Bound to the exact production standalone session factory (wiring proof).
    assert recorder._session_factory is get_session_factory()  # pyright: ignore[reportPrivateUsage]


async def test_coauthor_apply_factory_equips_production_recorder() -> None:
    """The co-author factory wires the same production recorder seam."""
    service = await get_coauthor_apply_service(session=AsyncMock())

    assert isinstance(service, CoAuthorApplyService)
    recorder = service._writing_stats_recorder  # pyright: ignore[reportPrivateUsage]
    assert isinstance(recorder, SqlWritingStatsRecorder)
    assert recorder._session_factory is get_session_factory()  # pyright: ignore[reportPrivateUsage]
