"""Application configuration — thin re-export hub.

All configuration comes from environment variables or .env file.
Never hardcode secrets — always use these settings classes.

For the actual Settings class definition, see ``settings_model.py``.
"""

from __future__ import annotations

from functools import lru_cache

from narrare._app.settings_model import BASE_DIR, ENV_FILE, Settings

__all__ = ["BASE_DIR", "ENV_FILE", "Settings", "get_settings"]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings.

    Use as FastAPI dependency: Depends(get_settings)
    """
    return Settings()
