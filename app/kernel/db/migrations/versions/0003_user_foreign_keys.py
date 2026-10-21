"""User foreign keys

Every user-owned row references the user it belongs to. The service guard keeps
writes out before setup; this key keeps orphans out of the database itself.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"

TABLES = ("novels", "chapters", "documents", "chunks")


def upgrade() -> None:
    for table in TABLES:
        op.create_foreign_key(
            f"fk_{table}_user_id", table, "users", ["user_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
