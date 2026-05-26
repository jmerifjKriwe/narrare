"""Unit tests for BetaReaderService — orchestration logic.

Tests split into separate files for RULE-04 compliance:
- test_beta_reader_analyze.py: Phase 1 cache hit/miss, response mapping
- test_beta_reader_deepdive.py: Phase 2 cache miss, word count validation
"""

# Re-export for pytest discovery and backward compatibility
from tests.unit.api.analysis.test_beta_reader_analyze import *  # noqa: F403
from tests.unit.api.analysis.test_beta_reader_deepdive import *  # noqa: F403
