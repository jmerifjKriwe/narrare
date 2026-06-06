"""Structured-logging evidence sink for AI invocation adoption.

Logs every :class:`~narrare_core.ai_invocation.models.FeatureInvocationEvidence`
as a structured JSON log line via structlog on INFO level. Implements the
:class:`~narrare_core.ai_invocation.contracts.FeatureInvocationEvidenceSink`
protocol.

Graceful degradation is inherent — structured logs are configurable and
filterable per deployment. No external I/O beyond structlog (non-blocking).

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-10/RULE-11.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import FeatureInvocationEvidence


class LoggingEvidenceSink:
    """Structured-logging implementation of ``FeatureInvocationEvidenceSink``.

    Records every evidence object as a structured log line on INFO level.
    All evidence fields are flattened into the log context for easy
    querying in log aggregation systems.

    This sink is async-awaitable but performs no I/O beyond structlog
    (which is non-blocking). Graceful degradation is inherent — structured
    logs are configurable and filterable per deployment.

    Args:
        logger_name: Name for the structlog logger. Defaults to
            ``"narrare.invocation.evidence"``.
        extra_fields: Optional static fields appended to every log
            line (e.g., ``{"version": "1.2.0", "environment": "prod"}``).
    """

    def __init__(
        self,
        *,
        logger_name: str = "narrare.invocation.evidence",
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        self._logger = structlog.get_logger(logger_name)
        self._extra_fields = extra_fields or {}

    async def record(self, evidence: FeatureInvocationEvidence) -> None:
        """Record invocation evidence as a structured log line.

        Flattens all evidence fields into the log context along with
        an ISO-8601 timestamp and any configured extra fields.

        Args:
            evidence: Privacy-safe evidence record from an AI invocation.
        """
        evidence_data = evidence.model_dump()
        timestamp = datetime.now(UTC).isoformat()

        # Merge: extra_fields as base, overridden by evidence_data, then timestamp.
        # This ensures evidence fields always take precedence over extra_fields.
        log_data: dict[str, object] = {
            **self._extra_fields,
            **evidence_data,
            "timestamp": timestamp,
        }

        self._logger.info("invocation_evidence", **log_data)
