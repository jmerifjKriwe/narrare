/**
 * Tasks API client tests — GET /tasks/status monitoring endpoint (INFRA-007).
 *
 * Verifies the typed client hits the right path and preserves the broker
 * status + registered task list returned by the backend.
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { tasksApi } from "../tasks";

const mockStatus = {
  broker_started: true,
  is_worker_process: false,
  registered_task_count: 7,
  registered_tasks: [
    "embed_source",
    "process_feedback_memory",
    "run_preference_analysis",
    "wiki_generate_chapter",
    "wiki_generate_entity",
    "wiki_mark_all_stale",
    "wiki_refresh_summary",
  ],
};

describe("tasksApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  describe("getStatus", () => {
    it("should GET /tasks/status and return the broker + task status", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/tasks/status", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(mockStatus);
        }),
      );

      const result = await tasksApi.getStatus();

      expect(capturedUrl).toContain("/api/v1/tasks/status");
      expect(result.broker_started).toBe(true);
      expect(result.is_worker_process).toBe(false);
      expect(result.registered_task_count).toBe(7);
      expect(result.registered_tasks).toHaveLength(7);
      expect(result.registered_tasks).toContain("embed_source");
      // The backend returns a sorted list; the client must preserve it verbatim.
      expect(result.registered_tasks).toEqual(mockStatus.registered_tasks);
    });

    it("should reflect a stopped broker (worker process)", async () => {
      server.use(
        http.get("*/api/v1/tasks/status", () =>
          HttpResponse.json({
            broker_started: false,
            is_worker_process: true,
            registered_task_count: 0,
            registered_tasks: [],
          }),
        ),
      );

      const result = await tasksApi.getStatus();

      expect(result.broker_started).toBe(false);
      expect(result.is_worker_process).toBe(true);
      expect(result.registered_task_count).toBe(0);
      expect(result.registered_tasks).toEqual([]);
    });

    it("should throw on a 500 error", async () => {
      server.use(
        http.get("*/api/v1/tasks/status", () =>
          HttpResponse.json({ detail: "Broker unavailable" }, { status: 500 }),
        ),
      );

      await expect(tasksApi.getStatus()).rejects.toThrow();
    });
  });
});
