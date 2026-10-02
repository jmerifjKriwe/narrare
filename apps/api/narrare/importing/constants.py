"""Import guardrails (ADR-091) — protocol constants, NOT user settings."""

from __future__ import annotations

from typing import Final

MAX_FILES: Final[int] = 100
MAX_FILE_BYTES: Final[int] = 5 * 1024 * 1024
MAX_TOTAL_BYTES: Final[int] = 25 * 1024 * 1024
ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset({".md", ".txt"})
