# apps/api/alembic/versions/0042_chat_project_optional.py
"""chat_conversations.project_id becomes nullable (NOTES-001 §6b).

Global notes have no project; chatting about them requires conversations
without a novel reference. This is the ONLY deliberate change to existing
chat behavior in NOTES-001 (spec §10) and is backward compatible: requests
carrying project_id behave exactly as before.

Downgrade data policy: project-less conversations (and their messages) are
DELETED before the NOT NULL restore — mirroring the 0037 pattern of removing
feature-dependent rows before constraint restoration; without the feature
they have no meaningful scope.

RULE-14: lands in the SAME task batch as the ChatConversation model change.

Revision ID: 0042_chat_project_optional
Revises: 0041_notes
Create Date: 2026-08-21 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0042_chat_project_optional"
down_revision: str | None = "0041_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("chat_conversations", "project_id", nullable=True)


def downgrade() -> None:
    # Remove rows the restored constraint would reject (documented data loss).
    op.execute(
        "DELETE FROM chat_messages WHERE conversation_id IN "
        "(SELECT id FROM chat_conversations WHERE project_id IS NULL)"
    )
    op.execute("DELETE FROM chat_conversations WHERE project_id IS NULL")
    op.alter_column("chat_conversations", "project_id", nullable=False)
