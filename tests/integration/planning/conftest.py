"""Shared fixtures for the planning integration tests.

The ``novel_and_chapter`` scene fixture is defined in
``_scenes_api_helpers.py`` and re-exported here so the scene API test
modules need no fixture imports (the kb-dir precedent — a fixture is
resolved by parameter name, not by import).
"""

from tests.integration.planning._scenes_api_helpers import (  # noqa: F401 — fixture registration
    novel_and_chapter,
)
