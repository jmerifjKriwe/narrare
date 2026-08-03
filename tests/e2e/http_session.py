"""Shared HTTP client for E2E direct API calls.

E2E tests make direct HTTP calls to the API (outside the browser) to seed
data (``register_unique_user``) and drive state changes (chapter CRUD via
``api_session``). The ``OriginValidationMiddleware``
(``apps/api/narrare/_app/middleware.py``, AUFG-05-13) rejects state-changing
requests that carry no ``Origin`` / ``Referer`` / ``Bearer`` token.

A real browser ALWAYS sends an ``Origin`` header. E2E direct calls must
therefore mimic a browser by sending the frontend page origin, otherwise
they break outside CI (CI sets ``ENVIRONMENT=test`` → ``is_test=True`` →
CSRF fully bypassed, which hides the fragility; locally, with CSRF active,
the same calls return ``403 CSRF_ORIGIN_MISMATCH``).

This module keeps the browser-mimic contract (``Origin`` + ``Referer``
defaults) in ONE place so the test infra matches production behaviour
instead of relying on CI's bypass. Per-call ``headers=`` (e.g.
``Authorization``) are MERGED with these defaults by ``requests`` — Origin
survives even when callers pass extra headers. That merge property is
guarded by ``tests/unit/test_e2e_http_session.py``.
"""

from __future__ import annotations

import requests


def build_api_session(origin: str) -> requests.Session:
    """Build a ``requests.Session`` that mimics a browser for direct API calls.

    Sets default ``Origin`` and ``Referer`` headers on every request so the
    CSRF ``OriginValidationMiddleware`` accepts state-changing calls
    (POST/PUT/PATCH/DELETE). Safe methods (GET/HEAD/OPTIONS) are already
    exempt, but routing them through the same session keeps the E2E HTTP
    layer consistent.

    Args:
        origin: The browser origin to mimic (e.g. ``"http://localhost:3000"``).
            Must match an entry in ``settings.csrf_trusted_origins`` so the
            middleware treats it as trusted.

    Returns:
        A configured :class:`requests.Session`. ``requests`` merges the
        session's default headers with any per-call ``headers=``, so callers
        can still pass ``Authorization`` / ``Content-Type`` without losing
        ``Origin``.
    """
    session = requests.Session()
    session.headers.update(
        {
            "Origin": origin,
            "Referer": f"{origin}/",
        }
    )
    return session
