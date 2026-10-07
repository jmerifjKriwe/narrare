# apps/api/narrare/analytics/_csv_format.py
"""CSV wire-format for usage-record exports (STATS-002 spec B-2/B-3/B-5).

Pure formatting helpers, split from the cost query service to keep it under
the RULE-04 service size limit. Owns the binding BOM + exact header column
order (spec B-3 — do not reorder) and the per-record line renderer: stdlib
``csv`` only (``aiocsv`` is deliberately not introduced, spec B-5), empty
cells for NULL cost/novel, exact ``Decimal`` money text, ISO-8601 UTC
timestamps. No I/O, no SQL, no HTTP.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare.analytics.models import UsageRecordRow

# BOM prefix so Excel opens the UTF-8 file correctly (spec B-2).
UTF8_BOM = "\ufeff"

# Header row in the exact binding column order (spec B-3).
CSV_COLUMNS: tuple[str, ...] = (
    "created_at",
    "intent",
    "provider",
    "model_id",
    "tokens_in",
    "tokens_out",
    "cache_read_tokens",
    "cache_creation_tokens",
    "duration_ms",
    "cost_usd",
    "novel_id",
)


def csv_line(values: tuple[object, ...] | list[object]) -> str:
    """Format ONE CSV record via stdlib ``csv`` (RFC 4180, CRLF-terminated)."""
    buffer = io.StringIO()
    csv.writer(buffer).writerow(values)
    return buffer.getvalue()


def header_line() -> str:
    """BOM + header row — the first line of every export (spec B-2)."""
    return UTF8_BOM + csv_line(list(CSV_COLUMNS))


def usage_record_line(row: UsageRecordRow) -> str:
    """One usage record as a CSV data line (spec B-3 column order).

    ``cost_usd`` NULL (unpriced) and ``novel_id`` NULL render as empty
    cells; money is the exact ``Decimal`` text (never float); ``created_at``
    is ISO-8601 normalized to UTC.
    """
    created = row.created_at
    if created.tzinfo is not None:
        created = created.astimezone(UTC)
    return csv_line(
        [
            created.isoformat(),
            row.intent,
            row.provider,
            row.model_id,
            row.tokens_in,
            row.tokens_out,
            row.cache_read_tokens,
            row.cache_creation_tokens,
            row.duration_ms,
            "" if row.cost_usd is None else str(row.cost_usd),
            "" if row.novel_id is None else str(row.novel_id),
        ]
    )
