"""Pure policy pins for the WS origin gate (N08 fix, production invariance).

The route-level behavior is pinned in test_router_sessions_validation.py;
these pins fix the POLICY so a future refactor cannot silently relax
production while fixing test mode (or vice versa).
"""

from __future__ import annotations

from narrare._app.config import Settings
from narrare.writing.ws_origin import origin_is_allowed

_TRUSTED = [
    "https://writing.example.org"
]  # non-default: allow-pins must be sensitive to the injected list


def _settings(environment: str) -> Settings:
    # Alias key: Settings uses extra="ignore" without populate_by_name, so a
    # field-name ``csrf_trusted_origins=`` ctor kwarg is silently DROPPED.
    return Settings.model_validate(
        {"environment": environment, "NARRARE_CSRF_TRUSTED_ORIGINS": _TRUSTED}
    )


def test_foreign_origin_rejected_in_production() -> None:
    assert origin_is_allowed("http://localhost:9999", _settings("production")) is False


def test_trusted_origin_allowed_in_production() -> None:
    assert origin_is_allowed(_TRUSTED[0], _settings("production")) is True


def test_empty_origin_allowed_in_production() -> None:
    assert origin_is_allowed("", _settings("production")) is True


def test_foreign_origin_rejected_in_development() -> None:
    """Dev keeps the strict posture too — only is_test relaxes (N08)."""
    assert origin_is_allowed("http://localhost:9999", _settings("development")) is False


def test_foreign_origin_allowed_in_test_environment() -> None:
    assert origin_is_allowed("http://localhost:9999", _settings("test")) is True
