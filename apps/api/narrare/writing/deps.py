"""Writing module dependency injection — re-exports from focused modules.

All dependencies are injected via __init__ (DI pattern).
No business logic lives here — only wiring.
"""

from narrare.writing.deps_coauthor import (
    get_coauthor_apply_service as get_coauthor_apply_service,
)
from narrare.writing.deps_coauthor import (
    get_coauthor_service as get_coauthor_service,
)
from narrare.writing.deps_extend import (
    get_extend_service as get_extend_service,
)
from narrare.writing.deps_rewrite import (
    get_rewrite_service as get_rewrite_service,
)
from narrare.writing.deps_style_variants import (
    get_style_variant_service as get_style_variant_service,
)
from narrare.writing.deps_suggest import (
    get_suggest_service as get_suggest_service,
)
from narrare.writing.deps_writing import (
    get_writing_service as get_writing_service,
)

__all__ = [
    "get_coauthor_apply_service",
    "get_coauthor_service",
    "get_extend_service",
    "get_rewrite_service",
    "get_style_variant_service",
    "get_suggest_service",
    "get_writing_service",
]
