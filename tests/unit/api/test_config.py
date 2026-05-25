"""Unit tests for _app/config.py — Settings environment-mode properties.

These properties are CRITICAL: a wrong mode detection could route writes to the
production database during tests, or disable safety features.  Every branch is
covered here with explicit assertions.
"""

from __future__ import annotations

import pytest

from narrare._app.config import Settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEV_DB = "postgresql+asyncpg://dev:dev@localhost:5432/dev"
_TEST_DB = "postgresql+asyncpg://test:test@localhost:5433/test"
_PROD_DB = "postgresql+asyncpg://prod:prod@localhost:5432/prod"


def _make_settings(**overrides: str) -> Settings:
    """Create a Settings instance with explicit values (no env-var lookup)."""
    defaults: dict[str, str] = {
        "database_url": _DEV_DB,
        "test_database_url": _TEST_DB,
        "secret_key": "test-secret-key-not-for-production-min-32",
    }
    defaults.update(overrides)
    # model_validate lets Pydantic handle type coercion (e.g. str → Literal)
    # so pyright doesn't flag dict[str,str] mismatches against typed fields.
    return Settings.model_validate(defaults)


# ===================================================================
# is_test
# ===================================================================


class TestIsTest:
    """Settings.is_test must be True *only* when environment == 'test'."""

    def test_returns_true_when_environment_is_test(self) -> None:
        settings = _make_settings(environment="test")
        assert settings.is_test is True

    def test_returns_false_when_environment_is_development(self) -> None:
        settings = _make_settings(environment="development")
        assert settings.is_test is False

    def test_returns_false_when_environment_is_production(self) -> None:
        settings = _make_settings(environment="production")
        assert settings.is_test is False

    def test_env_var_routing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ENVIRONMENT env var is correctly mapped to is_test."""
        monkeypatch.setenv("ENVIRONMENT", "test")
        settings = Settings(
            secret_key="test-secret-key-not-for-production-min-32",
        )
        assert settings.is_test is True


# ===================================================================
# is_development
# ===================================================================


class TestIsDevelopment:
    """Settings.is_development must be True *only* when environment == 'development'."""

    def test_returns_true_when_environment_is_development(self) -> None:
        settings = _make_settings(environment="development")
        assert settings.is_development is True

    def test_returns_false_when_environment_is_test(self) -> None:
        settings = _make_settings(environment="test")
        assert settings.is_development is False

    def test_returns_false_when_environment_is_production(self) -> None:
        settings = _make_settings(environment="production")
        assert settings.is_development is False

    def test_default_environment_is_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When ENVIRONMENT is unset, the default is 'development'."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        settings = Settings(
            secret_key="test-secret-key-not-for-production-min-32",
        )
        assert settings.is_development is True


# ===================================================================
# is_production
# ===================================================================


class TestIsProduction:
    """Settings.is_production must be True *only* when environment == 'production'.

    Safety check: is_production must NEVER be True when is_test is True.
    """

    def test_returns_true_when_environment_is_production(self) -> None:
        settings = _make_settings(environment="production")
        assert settings.is_production is True

    def test_returns_false_when_environment_is_development(self) -> None:
        settings = _make_settings(environment="development")
        assert settings.is_production is False

    def test_returns_false_when_environment_is_test(self) -> None:
        settings = _make_settings(environment="test")
        assert settings.is_production is False

    def test_never_true_when_is_test_is_true(self) -> None:
        """Safety: is_production and is_test must be mutually exclusive."""
        settings = _make_settings(environment="test")
        assert not (settings.is_production and settings.is_test)

    def test_env_var_routing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        settings = Settings(
            secret_key="test-secret-key-not-for-production-min-32",
        )
        assert settings.is_production is True


# ===================================================================
# active_database_url
# ===================================================================


class TestActiveDatabaseUrl:
    """active_database_url routes to the correct database string.

    Priority: test_database_url when is_test, else database_url.
    This is the single most critical property — a wrong URL means data loss.
    """

    def test_returns_test_database_url_when_is_test(self) -> None:
        settings = _make_settings(
            environment="test",
            database_url=_PROD_DB,
            test_database_url=_TEST_DB,
        )
        assert settings.active_database_url == _TEST_DB

    def test_returns_database_url_when_is_production(self) -> None:
        settings = _make_settings(
            environment="production",
            database_url=_PROD_DB,
            test_database_url=_TEST_DB,
        )
        assert settings.active_database_url == _PROD_DB

    def test_returns_database_url_when_is_development(self) -> None:
        settings = _make_settings(
            environment="development",
            database_url=_DEV_DB,
            test_database_url=_TEST_DB,
        )
        assert settings.active_database_url == _DEV_DB

    def test_test_mode_overrides_even_if_prod_url_set(self) -> None:
        """Even with a production database_url, test mode MUST use test_database_url."""
        settings = _make_settings(
            environment="test",
            database_url=_PROD_DB,
            test_database_url=_TEST_DB,
        )
        # The production URL exists but must NOT be used in test mode.
        assert settings.active_database_url == _TEST_DB
        assert settings.active_database_url != _PROD_DB

    def test_distinct_urls_prove_correct_routing(self) -> None:
        """With distinct URLs for each mode, verify the right one is picked."""
        # Development
        dev = _make_settings(
            environment="development",
            database_url=_DEV_DB,
            test_database_url=_TEST_DB,
        )
        assert dev.active_database_url == _DEV_DB

        # Test
        test = _make_settings(
            environment="test",
            database_url=_DEV_DB,
            test_database_url=_TEST_DB,
        )
        assert test.active_database_url == _TEST_DB

        # Production
        prod = _make_settings(
            environment="production",
            database_url=_PROD_DB,
            test_database_url=_TEST_DB,
        )
        assert prod.active_database_url == _PROD_DB


# ===================================================================
# Mode exclusivity
# ===================================================================


class TestModeExclusivity:
    """At most one of is_development / is_test / is_production is True.

    Because 'environment' is a Literal with three mutually exclusive values,
    exactly one mode must always be active.
    """

    @pytest.mark.parametrize(
        "env",
        ["development", "test", "production"],
    )
    def test_exactly_one_mode_active(self, env: str) -> None:
        settings = _make_settings(environment=env)
        modes = [settings.is_development, settings.is_test, settings.is_production]
        assert sum(modes) == 1, (
            f"Expected exactly 1 active mode for environment={env!r}, "
            f"got {sum(modes)}: dev={settings.is_development}, "
            f"test={settings.is_test}, prod={settings.is_production}"
        )

    @pytest.mark.parametrize(
        "env",
        ["development", "test", "production"],
    )
    def test_correct_mode_is_active(self, env: str) -> None:
        settings = _make_settings(environment=env)
        expected: dict[str, bool] = {
            "is_development": env == "development",
            "is_test": env == "test",
            "is_production": env == "production",
        }
        for prop_name, expected_val in expected.items():
            actual = getattr(settings, prop_name)
            assert actual is expected_val, (
                f"settings.{prop_name} = {actual!r} for environment={env!r}, "
                f"expected {expected_val!r}"
            )

    def test_no_mode_overlap_between_instances(self) -> None:
        """Three Settings instances with different environments never share a mode."""
        dev = _make_settings(environment="development")
        test = _make_settings(environment="test")
        prod = _make_settings(environment="production")

        # Each has exactly one True
        assert dev.is_development and not dev.is_test and not dev.is_production
        assert not test.is_development and test.is_test and not test.is_production
        assert not prod.is_development and not prod.is_test and prod.is_production
