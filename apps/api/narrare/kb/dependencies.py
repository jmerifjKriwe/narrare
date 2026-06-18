"""KB dependency injection — re-exports from focused modules.

All dependencies are injected via __init__ (DI pattern).
No business logic lives here — only wiring.
"""

from narrare.kb._consistency_deps import (
    get_consistency_service as get_consistency_service,
)
from narrare.kb.dependencies_core import (
    get_graph_service as get_graph_service,
)
from narrare.kb.dependencies_core import (
    get_kb_repository as get_kb_repository,
)
from narrare.kb.dependencies_core import (
    get_kb_service as get_kb_service,
)
from narrare.kb.dependencies_core import (
    get_kb_suggest_service as get_kb_suggest_service,
)
from narrare.kb.dependencies_core import (
    get_rel_repository as get_rel_repository,
)
from narrare.kb.dependencies_core import (
    get_rel_service as get_rel_service,
)
from narrare.kb.dependencies_extraction import (
    get_extraction_service as get_extraction_service,
)
from narrare.kb.dependencies_improve import (
    get_kb_improve_service as get_kb_improve_service,
)
from narrare.kb.dependencies_session import (
    get_kb_session_service as get_kb_session_service,
)
from narrare.kb.dependencies_worldbuilding import (
    get_worldbuilding_service as get_worldbuilding_service,
)
from narrare.kb.lifecycle_dependencies import (
    get_kb_lifecycle_dispatcher as get_kb_lifecycle_dispatcher,
)

__all__ = [
    "get_consistency_service",
    "get_extraction_service",
    "get_graph_service",
    "get_kb_improve_service",
    "get_kb_lifecycle_dispatcher",
    "get_kb_repository",
    "get_kb_service",
    "get_kb_session_service",
    "get_kb_suggest_service",
    "get_rel_repository",
    "get_rel_service",
    "get_worldbuilding_service",
]
