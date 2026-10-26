"""The durable background lane (spec §9 D10, D14).

A request enqueues a :class:`Job` on its own transaction — :func:`enqueue`
never commits — and the lane, one asyncio task the API lifespan starts
(:mod:`app.kernel.jobs.runtime`), claims queued rows with ``FOR UPDATE SKIP
LOCKED`` and runs a registered handler to done or failed. Capabilities never
touch the table directly: they enqueue through this seam and register handlers
in their ``jobs.py``, which the api app discovers by convention.

The table is kernel-internal machinery, so it lives in this package's
:mod:`models` and not in contracts.
"""

from app.kernel.jobs.models import Job, enqueue
from app.kernel.jobs.worker import JobHandler, ProgressReport, Worker

__all__ = ["Job", "JobHandler", "ProgressReport", "Worker", "enqueue"]
