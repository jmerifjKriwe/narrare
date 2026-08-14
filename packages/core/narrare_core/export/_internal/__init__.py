"""Internal tree transforms for the manuscript normalizer (Pure Core).

Each helper operates on a parsed BeautifulSoup tree — no string I/O, no
``apps/`` imports, no I/O, no subprocess (RULE-05). They are implementation
details of :class:`narrare_core.export.normalizer.NarrareNormalizer` and are
not part of the public export surface.
"""

from narrare_core.export._internal._normalize import (
    normalize_dialogue,
    normalize_scene_breaks,
)
from narrare_core.export._internal._strip import (
    strip_ai_annotation,
    strip_ghost_text,
)
from narrare_core.export._internal._structure import order_chapters

__all__ = [
    "normalize_dialogue",
    "normalize_scene_breaks",
    "order_chapters",
    "strip_ai_annotation",
    "strip_ghost_text",
]
