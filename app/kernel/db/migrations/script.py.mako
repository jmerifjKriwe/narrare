"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
<%!
def _pystr(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
%>
from collections.abc import Sequence

import pgvector.sqlalchemy  # pyright: ignore[reportUnusedImport]
import sqlalchemy as sa  # pyright: ignore[reportUnusedImport]
from alembic import op  # pyright: ignore[reportUnusedImport]
% if imports:
${imports}
% endif

revision: str = ${_pystr(up_revision)}
down_revision: str | Sequence[str] | None = ${_pystr(down_revision) if isinstance(down_revision, str) else "None" if down_revision is None else "(" + ", ".join(_pystr(item) for item in down_revision) + ("," if len(down_revision) == 1 else "") + ")"}
branch_labels: str | Sequence[str] | None = ${_pystr(branch_labels) if isinstance(branch_labels, str) else "None" if branch_labels is None else "(" + ", ".join(_pystr(item) for item in branch_labels) + ("," if len(branch_labels) == 1 else "") + ")"}
depends_on: str | Sequence[str] | None = ${_pystr(depends_on) if isinstance(depends_on, str) else "None" if depends_on is None else "(" + ", ".join(_pystr(item) for item in depends_on) + ("," if len(depends_on) == 1 else "") + ")"}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    raise RuntimeError("Narrare does not support downgrades (design D6).")
