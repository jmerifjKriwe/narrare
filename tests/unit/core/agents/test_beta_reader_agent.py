"""Tests for BetaReaderAgent — Phase 1 output parsing, instantiation, and edge cases.

Tests split into separate files for RULE-04 compliance:
- test_beta_reader_phase1.py: deps defaults, instantiation, run delegation
- test_beta_reader_validation.py: ADR-035 output validators (Phase 1 + Phase 2)
"""

# Re-export for pytest discovery and backward compatibility
from tests.unit.core.agents.test_beta_reader_phase1 import *  # noqa: F403
