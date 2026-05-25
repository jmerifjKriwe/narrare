"""Hero E2E Flow Test — complete MVP user journey.

Covers: registration → setup wizard (all steps) → dashboard → editor → autosave.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).

NOTE: This file has been split into focused modules for better maintainability.
See the individual test modules:
- test_auth_flow.py: Authentication flow tests
- test_setup_wizard.py: Setup wizard tests
- test_editor_autosave.py: Editor autosave tests
- test_helpers.py: Shared helper functions

The large test method below has been moved to the respective modules.
"""

from __future__ import annotations

import pytest


# Keep the original class name and structure for compatibility
@pytest.mark.e2e
class TestHeroFlow:  # type: ignore[misc]
    """Combined test class covering the complete MVP user journey.

    NOTE: Individual test cases are now in focused modules:
    - test_auth_flow.py: Authentication flow
    - test_setup_wizard.py: Setup wizard tests
    - test_editor_autosave.py: Editor autosave tests

    This class is kept for compatibility. Run individual test modules
    directly for precise test selection.
    """

    pass
