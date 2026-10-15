"""WS origin validation policy (CSRF defense-in-depth, AUFG-05-13 / ADR-084).

Pure decision helper extracted from ``router_sessions`` (RULE-04: the
router sits at the 150-line cap) so the origin policy is pinnable without
a live socket. Mirrors the REST seam: ``_app/main.py`` does not install
``OriginValidationMiddleware`` when ``settings.is_test`` — the WS gate
honors the same ``ENVIRONMENT=test`` rule (N08). Production deployments
keep the exact pre-fix posture: the bypass is ``is_test``-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare._app.settings_model import Settings


def origin_is_allowed(origin: str, settings: Settings) -> bool:
    """Return ``True`` when a WS connect carrying *origin* may proceed.

    Rules:
    * ``ENVIRONMENT=test`` → allowed (REST CSRF parity, N08).
    * Empty origin → allowed (non-browser clients; pre-fix behavior).
    * Otherwise → allowed iff listed in ``csrf_trusted_origins``.
    """
    if settings.is_test:
        return True
    if not origin:
        return True
    return origin in settings.csrf_trusted_origins
