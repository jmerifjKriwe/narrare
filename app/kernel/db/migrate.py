"""The migration history's read side.

Two things any consumer of the history needs: which revision is head, and
whether a database's schema still equals the models'. The gates in
``app/kernel/db/tests/test_migrations.py`` pin both, and the unattended
startup path builds on them. The metadata compared against is the models':
``env.py`` imports every model module for its registration side effect, and
a caller that compares outside alembic must have imported those modules the
same way — ``init.py`` and the gates' upgrade step do.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.kernel.db.base import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"


class MigrationRefused(RuntimeError):  # noqa: N818  the name is the task interface
    """The migration history cannot be read or applied as asked."""


def default_config() -> Config:
    """The repo's alembic.ini; the URL arrives via NARRE_DATABASE_URL in env.py."""
    return Config(str(ALEMBIC_INI))


def head_revision() -> str:
    """The one head of the migration history.

    Two heads mean someone committed a branch instead of extending the
    history; zero mean no revisions exist. Both refuse: an upgrade that
    guesses which line to follow is how a database ends up half-migrated.
    """
    heads = ScriptDirectory.from_config(default_config()).get_heads()
    if len(heads) != 1:
        raise MigrationRefused(
            f"expected exactly one head revision, found {len(heads)}: {', '.join(heads)}"
        )
    return heads[0]


def diff_against_models(config: Config, connection: Connection) -> list[Any]:
    """What alembic would still have to do for the database to match the models.

    An empty list means the migrated schema equals the models' — the gate
    that keeps the two schema paths (the replayed history, the models-built
    tests) saying the same thing. The comparison runs with the same switches
    an autogenerate draft runs with, so the gate proves what a draft would
    see.
    """
    context = MigrationContext.configure(
        connection, opts={"compare_type": True, "compare_server_default": True}
    )
    return list(compare_metadata(context, Base.metadata))
