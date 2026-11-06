"""The database connection, wherever its parts come from.

The container's whole configuration is six variables, and most of them are
forgiven: a user who already runs a Postgres types host, name and user into a
template, not a URL with a percent-encoded password. Precedence is one-way
(`NARRE_DATABASE_URL` wins), the assembled URL is built by SQLAlchemy's own URL
type so no password has to be escaped by hand, and the source of the connection
is a line an operator can read in the log.
"""

import pytest
from sqlalchemy.engine import make_url

from app.kernel.db.url import DatabaseConfigurationError, resolve

PARTS = {
    "NARRE_DB_HOST": "postgres",
    "NARRE_DB_NAME": "narrare",
    "NARRE_DB_USER": "narrare",
}


def test_a_given_url_wins_over_the_parts() -> None:
    config = resolve(
        {
            "NARRE_DATABASE_URL": "postgresql+asyncpg://u:p@elsewhere:5432/other",
            **PARTS,
        }
    )
    assert config.url.database == "other"
    assert config.url.host == "elsewhere"
    assert config.source == "NARRE_DATABASE_URL"


def test_the_parts_compose_a_url() -> None:
    config = resolve(PARTS)
    assert config.url.drivername == "postgresql+asyncpg"
    assert (config.url.host, config.url.port, config.url.database) == (
        "postgres",
        5432,
        "narrare",
    )
    assert config.source == "NARRE_DB_* → narrare@postgres:5432/narrare"


def test_a_password_survives_the_url_encoding() -> None:
    """`@`, `:` and `#` in a password are what a hand-written URL loses first."""
    config = resolve({**PARTS, "NARRE_DB_PASSWORD": "p@ss:w/rd#1"})
    rendered = config.url.render_as_string(hide_password=False)
    assert make_url(rendered).password == "p@ss:w/rd#1"


def test_the_source_never_carries_the_password() -> None:
    config = resolve({**PARTS, "NARRE_DB_PASSWORD": "p@ss:w/rd#1"})
    assert "rd#1" not in config.source


def test_an_ipv6_host_is_bracketed() -> None:
    config = resolve({**PARTS, "NARRE_DB_HOST": "fe80::1"})
    assert "[fe80::1]" in config.url.render_as_string(hide_password=False)


def test_no_password_is_a_connection_without_one() -> None:
    """Trust authentication is a legitimate server; the URL must not invent a blank."""
    config = resolve(PARTS)
    assert config.url.password is None


def test_an_incomplete_set_is_refused_by_name() -> None:
    with pytest.raises(DatabaseConfigurationError) as refused:
        resolve({"NARRE_DB_HOST": "postgres", "NARRE_DB_NAME": "narrare"})
    assert "NARRE_DB_USER" in str(refused.value)


def test_an_empty_value_counts_as_unset() -> None:
    """A template that renders an unset field as an empty string must not become a host."""
    with pytest.raises(DatabaseConfigurationError) as refused:
        resolve({**PARTS, "NARRE_DB_HOST": ""})
    assert "NARRE_DB_HOST" in str(refused.value)


def test_nothing_configured_falls_back_to_the_development_database() -> None:
    config = resolve({})
    assert config.url.database == "narrare_v2_dev"
    assert config.source == "default (localhost dev)"


def test_a_port_that_is_not_a_number_is_refused_by_name() -> None:
    with pytest.raises(DatabaseConfigurationError) as refused:
        resolve({**PARTS, "NARRE_DB_PORT": "5432x"})
    assert "NARRE_DB_PORT" in str(refused.value)


def test_an_unknown_sslmode_is_refused_by_name() -> None:
    with pytest.raises(DatabaseConfigurationError) as refused:
        resolve({**PARTS, "NARRE_DB_SSLMODE": "sometimes"})
    assert "NARRE_DB_SSLMODE" in str(refused.value)


def test_the_sslmode_reaches_asyncpg_as_its_own_parameter() -> None:
    config = resolve({**PARTS, "NARRE_DB_SSLMODE": "require"})
    assert config.url.query["ssl"] == "require"
