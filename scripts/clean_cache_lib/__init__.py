"""clean_cache_lib — modular cache-cleaner internals.

Split from ``scripts/clean_caches.py`` (RULE-04 modularization) to keep the
CLI entry point under the 600-line script limit. The entry point imports its
public API from here.

Public modules:
    data     — CleanStats, Category, CATEGORIES, CATEGORY_GROUPS, EXCLUDED_ROOTS
    ops      — safety helpers, size formatting, category-name resolution
    handlers — operation handlers, log cleanup, category orchestration

Public API surface
------------------
Only the names re-exported below are part of the supported interface between
the entry point and this package. Everything else — the cross-module helpers
(``is_excluded``, ``safe_rmtree``, ``safe_unlink``), the module-private
``_calculate_size``, and the ``_handle_*`` / ``_clean_logs`` handlers — are
shared internal implementation details of the package's own modules
(``ops.py``, ``handlers.py``) and are intentionally NOT re-exported.
"""

from .data import (
    CATEGORIES,
    CATEGORY_GROUPS,
    CATEGORY_INDEX,
    EXCLUDED_ROOTS,
    ROOT,
    Category,
    CleanStats,
)
from .handlers import clean_category
from .ops import (
    expand_categories,
    format_size,
)

__all__ = [
    "CATEGORIES",
    "CATEGORY_GROUPS",
    "CATEGORY_INDEX",
    "EXCLUDED_ROOTS",
    "ROOT",
    "Category",
    "CleanStats",
    "clean_category",
    "expand_categories",
    "format_size",
]
