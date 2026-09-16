"""Task 3e stream-factory wiring tests — request-row budget resolution.

C5 / ADR-082 enforcement evidence for the REAL stream call shape: the
stream route only knows ``request_id``, so the request-scoped factory
(:func:`narrare.writing.deps_writing_stream.get_writing_service_for_stream`)
must recover the novel from the generation-request row and resolve
ADR-082 Decision-6 budgets (series carve-out vs. standalone full total)
plus ownership on that basis.

RULE-04 note: this class is the module split of what the Task 3e brief
prescribed as an append to ``test_context_budget_wiring.py`` — the
append pushed that file past the 400-line hard limit (320 + 110 = 430).
The shared hermetic patch helpers stay in the original module; see the
task report for the flagged deviation. The factory itself moved to
``deps_writing_stream.py`` in the same RULE-04 spirit (fix-wave N1).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from tests.unit.api.writing.test_context_budget_wiring import (
    _budget_patch_context,
    _canned_budgets,
    _fake_session,
)


class TestStreamFactoryRequestScopedWiring:
    """Task 3e (final-review CRITICAL): the REAL stream call shape —
    request_id only, no project_id — must resolve budgets from the
    request row's novel (ADR-082 Decision 6 on the streaming path)."""

    async def test_series_novel_request_carves_series_history(self) -> None:
        import importlib
        from types import SimpleNamespace
        from unittest.mock import patch as _patch

        budgets = _canned_budgets(tier_base=20_000, series_history=12_000)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_writing", budgets
        )
        module = importlib.import_module("narrare.writing.deps_writing_stream")

        user_id = uuid.uuid4()
        row = SimpleNamespace(id=uuid.uuid4(), user_id=user_id, novel_id=uuid.uuid4())
        series_novel = SimpleNamespace(series_id=uuid.uuid4())
        with (
            ctx[0],
            ctx[1],
            ctx[2],
            ctx[3],
            ctx[4],
            _patch("narrare.writing.repository.GenerationRepository") as gen_repo_cls,
            _patch("narrare.novels.repository.NovelRepository") as novel_repo_cls,
        ):
            gen_repo_cls.return_value.get_by_id = AsyncMock(return_value=row)
            novel_repo_cls.return_value.get = AsyncMock(return_value=series_novel)
            # N1 gate: entry lookup must report the novel as owned.
            novel_repo_cls.return_value.get_by_id = AsyncMock(return_value=series_novel)
            service = await module.get_writing_service_for_stream(
                session=_fake_session(),
                user_id=str(user_id),
                request_id=row.id,
            )
            # ADR-086 L37: the budget/pipeline wiring happens at the
            # service's first use, not at factory time.
            runtime = await service.ensure_resolved()

        assert adapter_spy.call_args.kwargs["series_in_scope"] is True
        assert pipeline_spy.call_args.kwargs["total_budget"] == 20_000
        assert runtime.series_history_budget == 12_000

    async def test_standalone_novel_request_resolves_full_total(self) -> None:
        import importlib
        from types import SimpleNamespace
        from unittest.mock import patch as _patch

        budgets = _canned_budgets(tier_base=32_000, series_history=0)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_writing", budgets
        )
        module = importlib.import_module("narrare.writing.deps_writing_stream")

        user_id = uuid.uuid4()
        row = SimpleNamespace(id=uuid.uuid4(), user_id=user_id, novel_id=uuid.uuid4())
        standalone_novel = SimpleNamespace(series_id=None)
        with (
            ctx[0],
            ctx[1],
            ctx[2],
            ctx[3],
            ctx[4],
            _patch("narrare.writing.repository.GenerationRepository") as gen_repo_cls,
            _patch("narrare.novels.repository.NovelRepository") as novel_repo_cls,
        ):
            gen_repo_cls.return_value.get_by_id = AsyncMock(return_value=row)
            novel_repo_cls.return_value.get = AsyncMock(return_value=standalone_novel)
            # N1 gate: entry lookup must report the novel as owned.
            novel_repo_cls.return_value.get_by_id = AsyncMock(return_value=standalone_novel)
            service = await module.get_writing_service_for_stream(
                session=_fake_session(),
                user_id=str(user_id),
                request_id=row.id,
            )
            # ADR-086 L37: the budget/pipeline wiring happens at the
            # service's first use, not at factory time.
            runtime = await service.ensure_resolved()

        assert adapter_spy.call_args.kwargs["series_in_scope"] is False
        assert pipeline_spy.call_args.kwargs["total_budget"] == 32_000
        assert runtime.series_history_budget == 0

    async def test_foreign_user_request_raises_not_found(self) -> None:
        """Ownership is enforced before any budget resolution runs."""
        import importlib
        from types import SimpleNamespace
        from unittest.mock import patch as _patch

        import pytest

        from narrare_core.shared.errors import NotFoundError

        budgets = _canned_budgets(tier_base=32_000, series_history=0)
        ctx, _pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_writing", budgets
        )
        module = importlib.import_module("narrare.writing.deps_writing_stream")

        row = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), novel_id=uuid.uuid4())
        with (
            ctx[0],
            ctx[1],
            ctx[2],
            ctx[3],
            ctx[4],
            _patch("narrare.writing.repository.GenerationRepository") as gen_repo_cls,
        ):
            gen_repo_cls.return_value.get_by_id = AsyncMock(return_value=row)
            with pytest.raises(NotFoundError):
                await module.get_writing_service_for_stream(
                    session=_fake_session(),
                    user_id=str(uuid.uuid4()),  # different from row.user_id
                    request_id=row.id,
                )

        assert adapter_spy.call_args is None
