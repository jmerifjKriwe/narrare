"""KB benchmark runner area for the Narrare stack (ADR-083 carve-out).

Manually-only area: benchmark code never enters CI jobs, pre-commit gates
for the repo, coverage baselines, or adoption checks. Tests live in
``benchmark/tests/`` and run via ``uv run pytest benchmark/tests/``.

The runner speaks HTTP(S) to the production API only (see
``benchmark/docs/api-surface.md``); importing ``narrare_core`` here is
forbidden (co-evolution boundary — the runner must survive KB-internal
refactors).
"""

__version__ = "0.1.0"
