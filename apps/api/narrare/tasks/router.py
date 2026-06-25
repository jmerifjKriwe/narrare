"""Read-only monitoring endpoint for the TaskIQ background task queue (INFRA-007).

Exposes task/queue introspection for operators. Deliberately minimal: TaskIQ's
``ListQueueBroker`` has no queue-depth API, so only registered task names and
the broker process role are reported.
"""

from __future__ import annotations

from typing import TypedDict

from fastapi import APIRouter

from narrare.tasks.broker import broker

router = APIRouter(tags=["monitoring"])


class TaskStatusResponse(TypedDict):
    """Shape of the ``GET /tasks/status`` response.

    Attributes:
        broker_started: Operational proxy for "is the task infrastructure up".
            TaskIQ exposes no explicit started flag; in the API server process
            the broker is started by the application lifespan, so
            ``not is_worker_process`` is used. It is ``False`` only inside a
            dedicated taskiq worker process.
        is_worker_process: Whether this process is the taskiq worker.
        registered_task_count: Number of registered background tasks.
        registered_tasks: Sorted list of registered ``task_name`` labels.
    """

    broker_started: bool
    is_worker_process: bool
    registered_task_count: int
    registered_tasks: list[str]


@router.get("/tasks/status")
async def get_task_status() -> TaskStatusResponse:
    """Return the background task queue status (read-only).

    Reports the registered task names and the broker's process role. TaskIQ's
    ``ListQueueBroker`` has no queue depth API, so queue length is unavailable.
    """
    tasks = broker.get_all_tasks()
    return {
        "broker_started": not broker.is_worker_process,
        "is_worker_process": broker.is_worker_process,
        "registered_task_count": len(tasks),
        "registered_tasks": sorted(tasks.keys()),
    }
