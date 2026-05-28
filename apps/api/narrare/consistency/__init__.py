"""Consistency module — AI-powered cross-chapter and cross-entity consistency checking.

Provides:
- CONS-001 (Consistency Checker): Detects contradictions in characters, timeline,
  world facts, and plot logic across chapters and KB data.
- CONS-002 (Custom Consistency Rules): Planned — user-defined consistency rules.

Structure:
- ``contracts.py`` — ``ConsistencyCheckerProtocol`` service contract.
- ``schemas.py`` — Request/response Pydantic models.
- ``checker_service.py`` — Service implementation (ConsistencyCheckerService).
- ``dependencies.py`` — DI factory (get_consistency_service).
- ``router.py`` — HTTP routes (POST /consistency/check, POST /consistency/chapters/{id}/check).
"""
