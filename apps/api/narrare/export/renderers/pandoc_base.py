"""Shared pandoc subprocess helper — the SOLE site the ``pandoc`` binary is
invoked (RULE-08).

RULE-08 (mechanically enforced by
``scripts/architecture/_checkers/export_binary_confinement.py``): no module other
than this one and the two pandoc renderers (``pandoc_md.py``, ``pandoc_epub.py``)
that import from it may spawn a pandoc subprocess. This is the single place
``asyncio.create_subprocess_exec("pandoc", ...)`` will live.

**Slice 0 scope:** placeholder only — no subprocess call exists yet. The shared
invocation helper lands in Slice 3 (Markdown) and is extended in Slice 4 (EPUB).
"""

from __future__ import annotations

# The production render binary this adapter owns. Kept as a module-level name so
# the RULE-08 confinement checker's allowed-modules list
# (apps/api/narrare/export/renderers/pandoc_base.py) and the future subprocess
# argv share one SSOT for the binary name. Not invoked at Slice 0.
PANDOC_BINARY = "pandoc"
