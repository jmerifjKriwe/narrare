"""Shared Pydantic schemas used across core modules.

Placeholder for cross-cutting schemas that don't belong to a single
domain module (e.g. pagination, shared request/response envelopes).

Planned features:
- Shared pagination schema (cursor-based and offset)
- Generic result envelope for service-to-service communication
- Cross-module ID types and reference schemas
- Common validation mixins

See: docs/_shared/CONSTRAINTS.md (RULE-06 — one responsibility per file)
"""
