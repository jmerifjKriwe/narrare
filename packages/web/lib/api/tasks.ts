/**
 * Typed API client for the background task monitoring endpoint (INFRA-007).
 *
 * Read-only status for the TaskIQ broker. TaskIQ's ``ListQueueBroker``
 * exposes no queue-depth API, so only registered task names and the broker's
 * process role are reported by the backend.
 *
 * Mirrors ``apps/api/narrare/tasks/router.py`` → ``TaskStatusResponse``.
 */

import { fetchApi } from "./core";

// --- Types ------------------------------------------------------------------

/** Shape of the ``GET /tasks/status`` response. */
export interface TaskStatus {
  /** Operational proxy for "is the task infrastructure up" (``not is_worker_process``). */
  readonly broker_started: boolean;
  /** Whether this process is the dedicated taskiq worker. */
  readonly is_worker_process: boolean;
  /** Number of registered background tasks. */
  readonly registered_task_count: number;
  /** Sorted list of registered ``task_name`` labels. */
  readonly registered_tasks: readonly string[];
}

// --- Tasks API --------------------------------------------------------------

export const tasksApi = {
  /** Fetch read-only background task queue status. */
  getStatus: () => fetchApi<TaskStatus>("/tasks/status"),
};
