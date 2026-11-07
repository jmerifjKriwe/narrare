"""Where the database connection comes from, and in which order.

Two sources, one precedence: ``NARRE_DATABASE_URL`` when it is set, otherwise the
parts (``NARRE_DB_HOST``, ``NARRE_DB_NAME``, ``NARRE_DB_USER`` and their
optional companions), otherwise the development database. A container template
asks for host, name, user and password — not for a URL, where a password with
``@``, ``:`` or ``#`` has to be escaped by hand and fails in a way nobody can
read. The parts are assembled through SQLAlchemy's :class:`URL`, which does that
escaping itself; nothing here builds a DSN by concatenation.

The resolution reads the environment once, at import of :mod:`app.kernel.db.session`,
so a test sets its variables before the app is imported, as it always has.
"""

from dataclasses import dataclass
from os import environ
from typing import TYPE_CHECKING

from sqlalchemy.engine import URL, make_url

if TYPE_CHECKING:
    from collections.abc import Mapping

DRIVERNAME = "postgresql+asyncpg"
"""The one dialect: asyncpg, whichever source the URL came from."""

DEFAULT_URL = "postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_v2_dev"
"""`just dev`'s database; the source line says so instead of pretending."""

DEFAULT_SOURCE = "default (localhost dev)"

DEFAULT_PORT = 5432

SSL_MODES = frozenset({"disable", "allow", "prefer", "require", "verify-ca", "verify-full"})
"""What asyncpg accepts as ``ssl``, checked here so a typo fails at startup."""

_REQUIRED = ("host", "name", "user")
"""The parts a database cannot be reached without; the rest have defaults."""

_OPTIONAL = ("port", "password", "sslmode")


class DatabaseConfigurationError(RuntimeError):
    """The parts cannot be completed; the message names every missing variable."""


@dataclass(frozen=True)
class DatabaseConfig:
    """One resolved connection and a line saying where it came from."""

    url: URL
    source: str


def _variable(name: str) -> str:
    return f"NARRE_DB_{name.upper()}"


def _value(env: Mapping[str, str], name: str) -> str:
    """A part's value, with the whitespace a template leaves behind removed.

    Empty means unset, so a template that renders an unused field as ``""``
    cannot become a host or a database name.
    """
    return (env.get(_variable(name)) or "").strip()


def resolve(env: Mapping[str, str] | None = None) -> DatabaseConfig:
    """The effective connection: URL, else the parts, else the development default.

    ``NARRE_DEV_DB_PORT`` is a dev-only convenience for parallel checkouts: it
    overrides the port in every branch below (full URL wins, since a URL carries
    its own port), so a single knob moves the application connection together
    with the compose mapping.
    """
    source = environ if env is None else env

    given = (source.get("NARRE_DATABASE_URL") or "").strip()
    if given:
        return DatabaseConfig(url=make_url(given), source="NARRE_DATABASE_URL")

    # Dev-only port override for parallel checkouts; validated below.
    dev_port_raw = (source.get("NARRE_DEV_DB_PORT") or "").strip()
    dev_port: int | None = None
    if dev_port_raw:
        try:
            dev_port = int(dev_port_raw)
        except ValueError:
            raise DatabaseConfigurationError(
                f"NARRE_DEV_DB_PORT is not a port number: {dev_port_raw!r}"
            ) from None
        if not 1 <= dev_port <= 65535:
            raise DatabaseConfigurationError(
                f"NARRE_DEV_DB_PORT must be between 1 and 65535, not {dev_port}"
            )

    parts = {name: _value(source, name) for name in (*_REQUIRED, *_OPTIONAL)}
    password = source.get("NARRE_DB_PASSWORD") or ""
    # Whitespace-only reads as unset, like every other part: a template that
    # renders an unused field as spaces must not become a password. Anything
    # else is taken verbatim — a password may contain spaces, and trimming one
    # would hide the difference between a typo and the real secret.
    parts["password"] = password if password.strip() else ""

    # Fall back to the dev port when NARRE_DB_PORT is unset, so the single knob
    # keeps the application in step with the compose mapping. Only when another
    # part is present, so a lone NARRE_DEV_DB_PORT still lands on the default
    # branch below instead of being treated as an incomplete parts set.
    required_present = any(parts[name] for name in _REQUIRED)
    if not parts["port"] and dev_port_raw and required_present:
        parts["port"] = str(dev_port)

    if not any(parts.values()):
        # Nothing configured: development default, honouring NARRE_DEV_DB_PORT.
        base = make_url(DEFAULT_URL)
        if dev_port is not None:
            base = base.set(port=dev_port)
        return DatabaseConfig(url=base, source=DEFAULT_SOURCE)

    missing = [_variable(name) for name in _REQUIRED if not parts[name]]
    if missing:
        raise DatabaseConfigurationError(
            f"the database configuration is incomplete: set {', '.join(missing)}"
            " — or set NARRE_DATABASE_URL instead of the parts"
        )

    port = DEFAULT_PORT
    if parts["port"]:
        try:
            port = int(parts["port"])
        except ValueError:
            raise DatabaseConfigurationError(
                f"NARRE_DB_PORT is not a port number: {parts['port']!r}"
            ) from None
        if not 1 <= port <= 65535:
            raise DatabaseConfigurationError(
                f"NARRE_DB_PORT must be between 1 and 65535, not {port}"
            )

    query: dict[str, str] = {}
    if parts["sslmode"]:
        if parts["sslmode"] not in SSL_MODES:
            raise DatabaseConfigurationError(
                f"NARRE_DB_SSLMODE is not one of {', '.join(sorted(SSL_MODES))}:"
                f" {parts['sslmode']!r}"
            )
        query["ssl"] = parts["sslmode"]

    url = URL.create(
        DRIVERNAME,
        username=parts["user"],
        password=parts["password"] or None,
        host=parts["host"],
        port=port,
        database=parts["name"],
        query=query,
    )
    return DatabaseConfig(
        url=url,
        # Names the connection, never the secret in it.
        source=f"NARRE_DB_* → {parts['user']}@{parts['host']}:{port}/{parts['name']}",
    )
