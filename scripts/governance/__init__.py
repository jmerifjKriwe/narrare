"""Governance health-checking modules (ADR-047 Phase 2).

Modular components for review-finding coverage checks:

- :mod:`aufg_registry`   — parses ``aufg-registry.md`` into structured entries.
- :mod:`review_findings` — extracts candidate findings from ``review-*.md``.
- :mod:`governance_health` — matches findings against registry lifecycle entries.

Each module is single-purpose (RULE-06). The CLI entrypoint lives in
``scripts/check_governance_health.py`` and orchestrates the three modules
without duplicating their internal logic (RULE-07).
"""
