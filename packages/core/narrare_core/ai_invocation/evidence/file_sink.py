"""File-based evidence sink for AI invocation adoption.

Append-only JSON Lines evidence store.  Each
:class:`~narrare_core.ai_invocation.models.FeatureInvocationEvidence`
is written as one JSON line with an added timestamp field.

See:
    ADR-041, INFRA-013 §P3.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import FeatureInvocationEvidence


class FileEvidenceSink:
    """Append-only JSON Lines evidence sink.

    Writes each :class:`~narrare_core.ai_invocation.models.FeatureInvocationEvidence`
    as one JSON line to ``.evidence/invocations.jsonl``.  Non-blocking: I/O errors
    are logged but never block the invocation pipeline.

    Args:
        evidence_dir: Directory for evidence files.
            Defaults to ``REPO_ROOT / ".evidence"``.
        filename: Evidence file name.
            Defaults to ``"invocations.jsonl"``.
    """

    def __init__(
        self,
        *,
        evidence_dir: Path | str | None = None,
        filename: str = "invocations.jsonl",
    ) -> None:
        if evidence_dir is None:
            # Default to .evidence/ in project root
            evidence_dir = (
                Path(__file__).resolve().parent.parent.parent.parent.parent.parent / ".evidence"
            )
        self._evidence_dir = Path(evidence_dir)
        self._filename = filename
        self._logger = structlog.get_logger("narrare.invocation.evidence.file")

    async def record(self, evidence: FeatureInvocationEvidence) -> None:
        """Append evidence as a JSON line.

        On I/O error: logs a warning and returns (no exception).
        Never blocks the invocation pipeline.
        """
        try:
            self._evidence_dir.mkdir(parents=True, exist_ok=True)
            evidence_data = evidence.model_dump()
            evidence_data["timestamp"] = datetime.now(UTC).isoformat()
            line = json.dumps(evidence_data, sort_keys=True)

            file_path = self._evidence_dir / self._filename
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as exc:
            self._logger.warning(
                "evidence_file_write_failed",
                error=str(exc),
                feature_id=evidence.feature_id,
            )

    @property
    def evidence_path(self) -> Path:
        """Path to the evidence file."""
        return self._evidence_dir / self._filename
