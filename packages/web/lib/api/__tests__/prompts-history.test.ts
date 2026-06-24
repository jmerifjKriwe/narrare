/**
 * Tests for CR-AUFG-07-19 prompt-history API surface.
 *
 * The REST endpoints live under ``/prompts/{prompt_id}/history*`` and return
 * snake_case JSON mirroring the Pydantic schemas in
 * ``apps/api/narrare/prompts/schemas_prompt_history.py`` (RULE-17).
 *
 * NOTE on scope: the backend resolves ``scope`` deterministically to PROJECT
 * (``_DEFAULT_SCOPE`` in ``router_prompt_history.py``); it is NOT a query
 * parameter on any of these endpoints. The client therefore never sends it.
 */
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { setAccessToken } from "@/lib/api/client";
import { promptsApi } from "@/lib/api/prompts";
import { server } from "@/mocks/server";

const PROMPT_ID = "writing/en/new_chapter";

function revision(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "rev-0001",
    prompt_id: PROMPT_ID,
    scope: "project",
    content: "You are a helpful writing assistant.",
    content_hash: "abc123",
    actor_id: null,
    source: "edit",
    change_reason: null,
    restored_from_id: null,
    created_at: "2026-06-20T10:00:00Z",
    is_active: false,
    ...overrides,
  };
}

describe("promptsApi.listHistory", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("GET /prompts/{id}/history returns paginated revisions (snake_case)", async () => {
    let capturedUrl = "";
    server.use(
      http.get(`*/api/v1/prompts/${PROMPT_ID}/history`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({
          prompt_id: PROMPT_ID,
          scope: "project",
          total: 2,
          limit: 50,
          offset: 0,
          revisions: [revision({ id: "rev-0002", is_active: true }), revision({ id: "rev-0001" })],
        });
      }),
    );

    const result = await promptsApi.listHistory(PROMPT_ID, 50, 0);

    // Query params: limit + offset only (NO scope — RULE-17).
    expect(capturedUrl).toContain("limit=50");
    expect(capturedUrl).toContain("offset=0");
    expect(capturedUrl).not.toContain("scope=");
    expect(result.total).toBe(2);
    expect(result.revisions).toHaveLength(2);
    expect(result.revisions[0].is_active).toBe(true);
  });

  it("omits limit/offset query when not provided (backend defaults apply)", async () => {
    let capturedUrl = "";
    server.use(
      http.get(`*/api/v1/prompts/${PROMPT_ID}/history`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({
          prompt_id: PROMPT_ID,
          scope: "project",
          total: 0,
          limit: 50,
          offset: 0,
          revisions: [],
        });
      }),
    );

    await promptsApi.listHistory(PROMPT_ID);
    expect(capturedUrl).not.toContain("limit=");
    expect(capturedUrl).not.toContain("offset=");
  });

  it("throws on HTTP error", async () => {
    server.use(
      http.get(`*/api/v1/prompts/${PROMPT_ID}/history`, () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );

    await expect(promptsApi.listHistory(PROMPT_ID)).rejects.toThrow("Not found");
  });
});

describe("promptsApi.compareRevisions", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("GET /prompts/{id}/history/compare?from=&to= returns both contents", async () => {
    let capturedUrl = "";
    server.use(
      http.get(`*/api/v1/prompts/${PROMPT_ID}/history/compare`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({
          prompt_id: PROMPT_ID,
          from_id: "active",
          to_id: "rev-0001",
          from_source: "active",
          to_source: "edit",
          from_content: "old content",
          to_content: "new content",
        });
      }),
    );

    const result = await promptsApi.compareRevisions(PROMPT_ID, "active", "rev-0001");

    // Uses the backend query aliases `from` / `to` (NOT from_revision/to_revision).
    expect(capturedUrl).toContain("from=active");
    expect(capturedUrl).toContain("to=rev-0001");
    expect(result.from_content).toBe("old content");
    expect(result.to_content).toBe("new content");
    expect(result.from_id).toBe("active");
  });

  it("throws on HTTP error", async () => {
    server.use(
      http.get(`*/api/v1/prompts/${PROMPT_ID}/history/compare`, () =>
        HttpResponse.json({ detail: "Revision missing" }, { status: 404 }),
      ),
    );

    await expect(promptsApi.compareRevisions(PROMPT_ID, "active", "rev-x")).rejects.toThrow(
      "Revision missing",
    );
  });
});

describe("promptsApi.restoreRevision", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("POST /prompts/{id}/history/{revision}/restore returns restored revision", async () => {
    let capturedMethod = "";
    server.use(
      http.post(`*/api/v1/prompts/${PROMPT_ID}/history/rev-0001/restore`, async ({ request }) => {
        capturedMethod = request.method;
        return HttpResponse.json({
          prompt_id: PROMPT_ID,
          restored_revision: revision({
            id: "rev-0002",
            source: "restore",
            restored_from_id: "rev-0001",
          }),
          active_content: "restored content",
          previous_active_hash: "abc123",
        });
      }),
    );

    const result = await promptsApi.restoreRevision(PROMPT_ID, "rev-0001");

    expect(capturedMethod).toBe("POST");
    expect(result.active_content).toBe("restored content");
    expect(result.restored_revision.source).toBe("restore");
    expect(result.restored_revision.restored_from_id).toBe("rev-0001");
  });

  it("throws on HTTP error", async () => {
    server.use(
      http.post(`*/api/v1/prompts/${PROMPT_ID}/history/rev-0001/restore`, () =>
        HttpResponse.json({ detail: "Conflict" }, { status: 409 }),
      ),
    );

    await expect(promptsApi.restoreRevision(PROMPT_ID, "rev-0001")).rejects.toThrow("Conflict");
  });
});

describe("promptsApi.clearHistory", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("DELETE /prompts/{id}/history returns deleted_count (no scope query)", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    server.use(
      http.delete(`*/api/v1/prompts/${PROMPT_ID}/history`, ({ request }) => {
        capturedUrl = request.url;
        capturedMethod = request.method;
        return HttpResponse.json({
          prompt_id: PROMPT_ID,
          scope: "project",
          deleted_count: 7,
        });
      }),
    );

    const result = await promptsApi.clearHistory(PROMPT_ID);

    expect(capturedMethod).toBe("DELETE");
    // scope is resolved server-side — never sent by the client.
    expect(capturedUrl).not.toContain("scope=");
    expect(result.deleted_count).toBe(7);
  });

  it("throws on HTTP error", async () => {
    server.use(
      http.delete(`*/api/v1/prompts/${PROMPT_ID}/history`, () =>
        HttpResponse.json({ detail: "Forbidden" }, { status: 403 }),
      ),
    );

    await expect(promptsApi.clearHistory(PROMPT_ID)).rejects.toThrow("Forbidden");
  });
});
