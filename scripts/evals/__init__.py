"""Beta-reader eval instrument (spec 2026-09-14-beta-reader-eval-design.md).

Manual, human-triggered, real-chain eval drivers — sibling of
``scripts/probes/``. Consumes ``benchmark/`` corpus assets as files via paths
(never as code; spec §3 boundary). Kept out of CI by construction: pytest
``testpaths`` covers ``tests/`` only.
"""
