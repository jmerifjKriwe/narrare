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

from tests.e2e.test_auth_flow import TestAuthFlow
from tests.e2e.test_editor_autosave import TestEditorAutosave
from tests.e2e.test_setup_wizard import TestSetupWizard


# Keep the original class name and structure for compatibility
@pytest.mark.e2e
class TestHeroFlow(TestAuthFlow, TestSetupWizard, TestEditorAutosave):  # type: ignore[misc]
    """Combined test class covering the complete MVP user journey.

    This class now inherits from the individual test modules to maintain
    the original test structure while keeping code organized in focused files.
    """

    pass  # All methods are inherited from the parent test classes
