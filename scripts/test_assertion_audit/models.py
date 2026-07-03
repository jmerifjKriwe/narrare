"""Pydantic models for test assertion audit results.

Defines the data structures used throughout the audit pipeline:
category enum, individual findings, per-file reports, and the
aggregate audit report.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class WeaknessCategory(StrEnum):
    """Categories of weak test assertion patterns."""

    TRIVIAL_TRUTHY = "trivial_truthy"
    """``assert result`` where result has no field access or comparison."""

    IS_NOT_NONE_SOLE = "is_not_none_sole"
    """``assert result is not None`` as the *only* assertion in the test."""

    STATUS_CODE_ONLY = "status_code_only"
    """``assert response.status_code == N`` without ``model_validate``."""

    ASSERT_TRUE_LITERAL = "assert_true_literal"
    """``assert True`` or ``assert False`` — a dead test."""

    RESPONSE_JSON_TRUTHY = "response_json_truthy"
    """``assert response.json()`` without field access or schema check."""

    PYTEST_RAISES_NO_MATCH = "pytest_raises_no_match"
    """``pytest.raises(Exc)`` called without ``match=`` parameter."""

    MISSING_MODEL_VALIDATE = "missing_model_validate"
    """Integration test checks ``status_code`` but never calls ``model_validate``."""


# Map category → human-readable fix recommendation.
RECOMMENDATIONS: dict[WeaknessCategory, str] = {
    WeaknessCategory.TRIVIAL_TRUTHY: (
        "Replace with a specific assertion, e.g., "
        "``assert result is True`` or ``assert len(result) > 0``"
    ),
    WeaknessCategory.IS_NOT_NONE_SOLE: (
        'Add a more specific assertion about the value, e.g., ``assert result.status == "active"``'
    ),
    WeaknessCategory.STATUS_CODE_ONLY: (
        "Validate the response body with ``model_validate``, "
        "e.g., ``data = ResponseModel.model_validate(response.json())``"
    ),
    WeaknessCategory.ASSERT_TRUE_LITERAL: (
        "Remove this dead assertion or replace it with a real check"
    ),
    WeaknessCategory.RESPONSE_JSON_TRUTHY: (
        "Validate the JSON structure, "
        "e.g., ``data = ResponseModel.model_validate(response.json())``"
    ),
    WeaknessCategory.PYTEST_RAISES_NO_MATCH: (
        "Add ``match=`` parameter to ``pytest.raises``, "
        'e.g., ``pytest.raises(ValueError, match="expected message")``'
    ),
    WeaknessCategory.MISSING_MODEL_VALIDATE: (
        "Add ``model_validate`` calls to validate response schemas"
    ),
}


class Finding(BaseModel):
    """A single weak assertion finding within a test file."""

    category: WeaknessCategory
    """The pattern category that was detected."""

    file_path: Path
    """Path to the file containing the weak assertion."""

    line: int
    """Line number where the weak assertion was detected."""

    code_snippet: str = Field(max_length=200)
    """Relevant source code snippet (up to 200 characters)."""

    weight: float = Field(ge=0.0, le=1.0)
    """Severity weight: 0.0 = harmless, 1.0 = guaranteed weak."""

    recommendation: str
    """Human-readable fix suggestion."""


class FileReport(BaseModel):
    """Per-file audit result."""

    file_path: Path
    """Path to the scanned test file."""

    total_assertions: int
    """Total number of assertion statements in the file."""

    findings: list[Finding]
    """All weak assertion findings in this file."""

    score: float = Field(ge=0.0, le=1.0)
    """Aggregate weakness score: 0 = perfect, 1 = all assertions weak."""


class AuditReport(BaseModel):
    """Complete audit result across all scanned files."""

    files: list[FileReport]
    """Per-file reports."""

    summary: str
    """Markdown-formatted summary of the audit."""

    total_findings: int
    """Total number of weak assertion findings across all files."""

    total_files_scanned: int
    """Total number of files that were scanned."""
