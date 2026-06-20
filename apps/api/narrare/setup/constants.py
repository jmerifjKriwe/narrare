"""Setup module constants — single source of truth for default values.

Constants in this module are imported by all setup-related files to
avoid hardcoded duplicates. Change requires verifying the local-first
assumption still holds.
"""

from __future__ import annotations

from datetime import date

OLLAMA_DEFAULT_URL: str = "http://localhost:11434"
"""Default Ollama base URL. Single source of truth.

Change requires verifying local-first assumption still holds.
"""

# ---------------------------------------------------------------------------
# Model catalog provenance labels — CR-AUFG-08-06
#
# These constants label whether a model list came from a live provider API
# or from the bundled fallback catalog. The setup API surfaces them through
# AvailableModelsResponse.provenance so clients can render
# "stale/offline fallback" explicitly instead of implying a calibrated list.
# ---------------------------------------------------------------------------

LIVE_CATALOG_SOURCE: str = "live"
"""Source label for models fetched from a live provider API in real time."""

FALLBACK_CATALOG_SOURCE: str = "bundled-fallback"
"""Source label for the static, bundled fallback model list.

This list ships with the application and is only used when the live
provider API is unreachable. It must be labelled so users know the
data may be stale.
"""

FALLBACK_CATALOG_LAST_REVIEWED: date = date(2025, 10, 1)
"""When the bundled fallback model list was last reviewed for freshness.

Update this date whenever the fallback catalog entries in
``provider_service._FALLBACK_MODELS`` are refreshed. The API exposes
it so clients can show "last reviewed October 2025".
"""
