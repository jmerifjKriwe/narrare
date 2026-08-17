"""Registration tests for the DOCX format (C3).

Pins that the renderer is wired into BOTH registration sites — the DI
factory (request path: ``list_formats`` / fast-fail availability) and the
background runner's lazy renderer map (the path real exports walk) — and
that the graceful binary-absence degradation covers DOCX like its siblings.
"""

from __future__ import annotations

import asyncio
import shutil
from typing import TYPE_CHECKING

from narrare.export import tasks
from narrare.export.dependencies import get_export_renderers
from narrare.export.options import ExportFormat
from narrare.export.renderers.pandoc_docx import PandocDocxRenderer
from narrare.export.service import ExportServiceImpl
from tests.unit.api.export.conftest import RecordingEnqueuer

if TYPE_CHECKING:
    import pytest


class TestDiFactoryRegistration:
    def test_get_export_renderers_includes_docx(self) -> None:
        renderers = get_export_renderers()

        assert set(renderers) == {
            ExportFormat.PDF,
            ExportFormat.EPUB,
            ExportFormat.MARKDOWN,
            ExportFormat.DOCX,
        }
        assert isinstance(renderers[ExportFormat.DOCX], PandocDocxRenderer)
        assert renderers[ExportFormat.DOCX].format is ExportFormat.DOCX


class TestRunnerRegistration:
    def test_resolve_runner_deps_includes_docx(self) -> None:
        saved = tasks._renderers
        tasks._renderers = None  # force lazy rebuild with the new adapter
        try:
            _normalizer, renderers = tasks._resolve_runner_deps()
            assert ExportFormat.DOCX in renderers
            assert isinstance(renderers[ExportFormat.DOCX], PandocDocxRenderer)
        finally:
            tasks._renderers = saved


class TestServiceAvailabilitySurface:
    """RULE-11 graceful degradation: DOCX availability tracks pandoc."""

    def _service(self) -> ExportServiceImpl:
        return ExportServiceImpl(
            renderers=get_export_renderers(),
            enqueue=RecordingEnqueuer(),
        )

    def test_docx_reported_unavailable_when_pandoc_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: None)
        formats = dict(asyncio.run(self._service().list_formats()))
        assert formats[ExportFormat.DOCX] is False

    def test_docx_reported_available_when_pandoc_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/bin/pandoc")
        formats = dict(asyncio.run(self._service().list_formats()))
        assert formats[ExportFormat.DOCX] is True
