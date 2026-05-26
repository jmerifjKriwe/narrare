"""Tests for BetaReaderAgent — Phase 1/2 output parsing, instantiation, and edge cases.

Tests split into separate files for RULE-04 compliance:
- test_beta_reader_phase1.py: Phase 1 output parsing, deps defaults, instantiation
- test_beta_reader_phase2.py: Phase 2 output parsing, score clamping
"""

# Re-export for pytest discovery and backward compatibility
from tests.unit.core.agents.test_beta_reader_phase1 import *  # noqa: F403
from tests.unit.core.agents.test_beta_reader_phase2 import *  # noqa: F403
