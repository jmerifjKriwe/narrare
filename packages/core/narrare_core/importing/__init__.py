# packages/core/narrare_core/importing/__init__.py
"""Pure chapter-detection engine for project import (SETUP-003, ADR-091)."""

from narrare_core.importing.candidates import (
    SPLIT_CANDIDATES_MAX,
    SplitCandidate,
    find_split_candidates,
)
from narrare_core.importing.detector import detect_chapters
from narrare_core.importing.models import CHAPTER_STATUSES, TITLE_MAX_LENGTH, DetectedChapter
from narrare_core.importing.operations import (
    ImportOperationSet,
    MergeOperation,
    SplitOperation,
    apply_operations,
    build_operation_set,
    validate_operations,
)

__all__ = [
    "CHAPTER_STATUSES",
    "SPLIT_CANDIDATES_MAX",
    "TITLE_MAX_LENGTH",
    "DetectedChapter",
    "ImportOperationSet",
    "MergeOperation",
    "SplitCandidate",
    "SplitOperation",
    "apply_operations",
    "build_operation_set",
    "detect_chapters",
    "find_split_candidates",
    "validate_operations",
]
