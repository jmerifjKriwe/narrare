"""TTL sweep semantics for the in-memory bulk extraction registry (ADR-092 §6).

Covers: terminal jobs swept only after ``BULK_JOB_TTL``, running/pending
jobs never swept, and the resume interplay — ``reset_for_resume`` withdraws
the ``expires_hint``, so a resumed job survives a far-future sweep. Split
out of ``test_registry.py`` along the module's real axis (request-path
semantics vs the background GC) to stay under the RULE-04 hard limit;
shares its factories via ``_registry_helpers``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from narrare.kb.bulk_extraction import registry, registry_store
from narrare.kb.bulk_extraction.contracts import BULK_JOB_TTL
from narrare.kb.bulk_extraction.schemas import BulkJobStatus
from narrare_core.shared.errors import NotFoundError
from tests.unit.api.kb.bulk_extraction._registry_helpers import (
    FROZEN_NOW as _FROZEN_NOW,
)
from tests.unit.api.kb.bulk_extraction._registry_helpers import OWNER
from tests.unit.api.kb.bulk_extraction._registry_helpers import (
    TERMINAL as _TERMINAL,
)
from tests.unit.api.kb.bulk_extraction._registry_helpers import (
    drive_to as _drive_to,
)
from tests.unit.api.kb.bulk_extraction._registry_helpers import (
    make_job as _make_job,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture(autouse=True)
def _clear_jobs() -> None:
    """Registry state is process-global — every test starts empty."""
    registry._JOBS.clear()


class TestSweep:
    @pytest.fixture(autouse=True)
    def _frozen_now(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Free time in BOTH modules (each binds its own ``_now``/``utc_now`` name)."""
        monkeypatch.setattr(registry, "_now", lambda: _FROZEN_NOW)
        monkeypatch.setattr(registry_store, "utc_now", lambda: _FROZEN_NOW)

    @staticmethod
    def _sweeper(hours_after_now: float) -> Callable[[], datetime]:
        return lambda: _FROZEN_NOW + timedelta(hours=hours_after_now)

    @pytest.mark.parametrize("terminal", _TERMINAL)
    def test_terminal_job_swept_only_after_ttl(self, terminal: BulkJobStatus) -> None:
        job_id = _make_job(0)
        _drive_to(job_id, terminal)
        assert registry.sweep_expired(now=self._sweeper(1)) == 0  # inside the 24 h TTL
        assert registry.status(job_id, OWNER).job_id == job_id
        assert registry.sweep_expired(now=self._sweeper(25)) == 1  # BULK_JOB_TTL elapsed
        with pytest.raises(NotFoundError):
            registry.status(job_id, OWNER)

    def test_running_job_never_swept(self) -> None:
        job_id = _make_job(0)
        registry.mark_job_running(job_id)
        assert registry.sweep_expired(now=self._sweeper(10_000)) == 0
        assert registry.status(job_id, OWNER).status is BulkJobStatus.RUNNING

    def test_pending_job_never_swept(self) -> None:
        job_id = _make_job(0)
        assert registry.sweep_expired(now=self._sweeper(10_000)) == 0
        assert registry.status(job_id, OWNER).status is BulkJobStatus.PENDING

    def test_resumed_job_is_withdrawn_from_sweep(self) -> None:
        """Resume withdraws ``expires_hint`` — a resumed job is never swept.

        Interplay pin (spec §4.5): a terminal job arms the hint; the resume
        reset withdraws it, so a far-future sweep must not drop the now
        non-terminal job.
        """
        job_id = _make_job(0)
        registry.mark_job_failed(job_id, "boom")  # terminal → hint armed
        registry.reset_for_resume(job_id, OWNER)  # hint withdrawn
        assert registry.sweep_expired(now=self._sweeper(10_000)) == 0
        assert registry.status(job_id, OWNER).status is BulkJobStatus.PENDING

    def test_ttl_is_the_contract_constant(self) -> None:
        assert BULK_JOB_TTL.total_seconds() == 24 * 3600
