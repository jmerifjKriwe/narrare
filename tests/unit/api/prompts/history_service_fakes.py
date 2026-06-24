"""Fakes for ``PromptHistoryApiService`` unit tests (CR-AUFG-07-19).

Mirrors the ``live_test_service_fakes.py`` pattern.  ``FakeCore`` models the
core ``PromptManagementService`` version-injection behaviour abstractly; the
written file content differs from the submitted content by ``_VERSION_MARKER``
exactly like the real core adds ``override_of_version`` frontmatter.
``FakeRepo`` is an in-memory stand-in for ``PromptHistoryRepository`` with
monotonically increasing ``created_at`` for deterministic ordering.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from narrare.prompts.models import PromptRevision
from narrare_core.prompts._management_types import PromptDetail

if TYPE_CHECKING:
    from collections.abc import Sequence

# The fake models "version injection" abstractly: the written file content
# differs from the submitted content by this marker, mirroring the real core
# service adding ``override_of_version`` frontmatter.
VERSION_MARKER = '\noverride_of_version: "1.0.0"\n'


def hash_text(text: str) -> str:
    """sha256 hex of ``text`` — mirrors ``history_mapping.content_hash``."""
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


class FakeCore:
    """In-memory stand-in for core ``PromptManagementService``."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.save_calls: list[tuple[str, str]] = []

    async def save_override(self, prompt_id: str, content: str) -> None:
        self.save_calls.append((prompt_id, content))
        self.files[prompt_id] = content + VERSION_MARKER

    async def get_prompt(self, prompt_id: str) -> PromptDetail | None:
        if prompt_id in self.files:
            return PromptDetail(
                prompt_id=prompt_id,
                content=self.files[prompt_id],
                base_content="bundled base",
                source="project",
                is_overridden=True,
                variables=[],
                metadata={"override_of_version": "1.0.0"},
            )
        return PromptDetail(
            prompt_id=prompt_id,
            content="bundled base",
            base_content="bundled base",
            source="bundled",
            is_overridden=False,
            variables=[],
            metadata={},
        )


class FakeRepo:
    """In-memory stand-in for ``PromptHistoryRepository``."""

    def __init__(self) -> None:
        self.rows: list[PromptRevision] = []
        self._counter = 0
        self.insert_calls = 0
        self.fail_next_insert: Exception | None = None

    def _ts(self) -> datetime:
        self._counter += 1
        return datetime(2024, 1, 1, tzinfo=UTC) + timedelta(seconds=self._counter)

    async def insert_revision(
        self,
        prompt_id: str,
        scope: str,
        *,
        content: str,
        content_hash: str,
        actor_id: uuid.UUID | None,
        source: str,
        change_reason: str | None = None,
        restored_from_id: uuid.UUID | None = None,
    ) -> PromptRevision:
        self.insert_calls += 1
        if self.fail_next_insert is not None:
            exc = self.fail_next_insert
            self.fail_next_insert = None
            raise exc
        rev = PromptRevision(
            prompt_id=prompt_id,
            scope=scope,
            content=content,
            content_hash=content_hash,
            actor_id=actor_id,
            source=source,
            change_reason=change_reason,
            restored_from_id=restored_from_id,
            created_at=self._ts(),
        )
        rev.id = uuid.uuid4()
        self.rows.append(rev)
        return rev

    async def get_latest_revision(self, prompt_id: str, scope: str) -> PromptRevision | None:
        matching = [r for r in self.rows if r.prompt_id == prompt_id and r.scope == scope]
        return matching[-1] if matching else None

    async def list_revisions(
        self,
        prompt_id: str,
        scope: str,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[PromptRevision]:
        matching = [r for r in self.rows if r.prompt_id == prompt_id and r.scope == scope]
        ordered = sorted(matching, key=lambda r: r.created_at, reverse=True)
        return list(ordered[offset : offset + limit])

    async def get_revision(self, revision_id: uuid.UUID) -> PromptRevision | None:
        for r in self.rows:
            if r.id == revision_id:
                return r
        return None

    async def count(self, prompt_id: str, scope: str) -> int:
        return sum(1 for r in self.rows if r.prompt_id == prompt_id and r.scope == scope)

    async def delete_history(self, prompt_id: str, scope: str) -> int:
        before = await self.count(prompt_id, scope)
        self.rows = [r for r in self.rows if not (r.prompt_id == prompt_id and r.scope == scope)]
        return before

    async def enforce_retention(
        self,
        prompt_id: str,
        scope: str,
        *,
        keep: int = 100,
    ) -> int:
        matching = [r for r in self.rows if r.prompt_id == prompt_id and r.scope == scope]
        if len(matching) <= keep:
            return 0
        ordered = sorted(matching, key=lambda r: r.created_at, reverse=True)[:keep]
        keep_ids = {r.id for r in ordered}
        to_delete = {r.id for r in matching if r.id not in keep_ids}
        self.rows = [r for r in self.rows if r.id not in to_delete]
        return len(to_delete)
