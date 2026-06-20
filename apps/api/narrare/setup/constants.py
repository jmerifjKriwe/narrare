"""Setup module constants — single source of truth for default values.

Constants in this module are imported by all setup-related files to
avoid hardcoded duplicates. Change requires verifying the local-first
assumption still holds.
"""

from __future__ import annotations

OLLAMA_DEFAULT_URL: str = "http://localhost:11434"
"""Default Ollama base URL. Single source of truth.

Change requires verifying local-first assumption still holds.
"""
