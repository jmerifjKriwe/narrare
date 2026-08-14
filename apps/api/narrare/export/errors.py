"""Export error types.

Extracted from :mod:`narrare.export.contracts` to keep file sizes under the
RULE-04 limit (mirrors ``analysis/errors.py``). All export-domain exceptions
live here. RULE-11 requires every failure to convert to a typed domain error;
these are the named children of :class:`ExportError`.
"""

from __future__ import annotations


class ExportError(Exception):
    """Base for all export-domain errors."""


class ExportFormatUnavailableError(ExportError):
    """Binary for the requested format is missing (RULE-11 graceful degradation).

    Raised synchronously by ``ExportService.export()`` — the client gets an
    immediate structured error instead of polling a doomed job.
    """


class ExportJobNotFoundError(ExportError):
    """Unknown job_id (e.g. lost on restart — D1)."""


class ExportArtifactExpiredError(ExportError):
    """Artifact token already consumed or TTL-expired."""


class ExportRenderError(ExportError):
    """A renderer subprocess failed. Wraps the format + a stderr tail."""
