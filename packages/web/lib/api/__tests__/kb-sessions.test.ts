/**
 * KB Sessions API client tests.
 *
 * All operations are plain REST (F9-2 transport fix): the backend's
 * suggest/interview/enhance routes return aggregate JSON documents, so the
 * client maps those documents instead of parsing SSE frames. Mocks live at
 * the fetchApi/MSW boundary — no module-level transport mocks.
 */

import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { kbSessionApi, requestEnhance, requestInterview, suggestField } from "../kb-sessions";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sessionResponse(overrides: Record<string, unknown> = {}) {
  return {
    id: "session-1",
    novel_id: "novel-1",
    user_id: "u1",
    entity_type: "character",
    status: "active",
    name: null,
    fields: [],
    context_entries: [],
    created_at: "",
    updated_at: "",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("kbSessionApi (REST)", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("createSession", () => {
    it("POST /novels/:novelId/kb/sessions and returns session", async () => {
      const result = await kbSessionApi.createSession("novel-1", "character");

      expect(result.id).toBe("kb-session-1");
      expect(result.novel_id).toBe("novel-1");
      expect(result.entity_type).toBe("character");
      expect(result.status).toBe("active");
      expect(result.fields.length).toBeGreaterThan(0);
    });

    it("sends entity_type in request body", async () => {
      server.use(
        http.post("*/api/v1/novels/:novelId/kb/sessions", async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(
            sessionResponse({ id: "custom", entity_type: body.entity_type as string }),
            { status: 201 },
          );
        }),
      );

      const result = await kbSessionApi.createSession("novel-1", "location");
      expect(result.entity_type).toBe("location");
    });

    it("throws on network error", async () => {
      server.use(
        http.post("*/api/v1/novels/:novelId/kb/sessions", async () => HttpResponse.error()),
      );

      await expect(kbSessionApi.createSession("novel-1", "character")).rejects.toThrow();
    });
  });

  describe("getSession", () => {
    it("GET /novels/:novelId/kb/sessions/:sessionId", async () => {
      const result = await kbSessionApi.getSession("novel-1", "kb-session-1");

      expect(result.id).toBe("kb-session-1");
      expect(result.status).toBe("active");
    });

    it("throws 404 for unknown sessions", async () => {
      server.use(
        http.get("*/api/v1/novels/:novelId/kb/sessions/:sessionId", async () =>
          HttpResponse.json({ detail: "Not found" }, { status: 404 }),
        ),
      );

      await expect(kbSessionApi.getSession("novel-1", "nonexistent")).rejects.toThrow("Not found");
    });
  });

  describe("answerField", () => {
    it("PATCH /novels/:novelId/kb/sessions/:sessionId/fields/:fieldKey", async () => {
      const result = await kbSessionApi.answerField("novel-1", "session-1", "name", "Anna");

      expect(result.fields[0].field_key).toBe("name");
      expect(result.fields[0].final_value).toBe("Anna");
    });
  });

  describe("completeSession", () => {
    it("sends the collected entry name in the request body (F9-1)", async () => {
      let captured: Record<string, unknown> | null = null;
      server.use(
        http.post(
          "*/api/v1/novels/:novelId/kb/sessions/:sessionId/complete",
          async ({ request }) => {
            captured = (await request.json()) as Record<string, unknown>;
            return HttpResponse.json({
              session: sessionResponse({ status: "complete", name: "Sir Aldric" }),
              entry_id: "kb-entry-new-123",
            });
          },
        ),
      );

      const result = await kbSessionApi.completeSession("novel-1", "session-1", "Sir Aldric");

      expect(captured).toEqual({ name: "Sir Aldric" });
      expect(result.session.status).toBe("complete");
      expect(result.entry_id).toBe("kb-entry-new-123");
    });

    it("completing without a name hits the backend's name guard", async () => {
      // Default MSW handler emulates the BE: absent body/name → 400.
      await expect(kbSessionApi.completeSession("novel-1", "session-1")).rejects.toThrow(
        "Session must have a name before completion",
      );
    });

    it("throws on server error", async () => {
      server.use(
        http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/complete", async () =>
          HttpResponse.json({ detail: "Session already completed" }, { status: 409 }),
        ),
      );

      await expect(
        kbSessionApi.completeSession("novel-1", "session-1", "Sir Aldric"),
      ).rejects.toThrow("Session already completed");
    });
  });

  describe("abandonSession", () => {
    it("DELETE /novels/:novelId/kb/sessions/:sessionId", async () => {
      const result = await kbSessionApi.abandonSession("novel-1", "session-1");

      expect(result).toBeUndefined();
    });
  });
});

describe("suggestField (REST)", () => {
  it("maps the aggregate JSON response to the suggestion result", async () => {
    const result = await suggestField("novel-1", "session-1", "description");

    expect(result).toEqual({
      field_key: "description",
      suggestion: "A brave adventurer seeking their destiny.",
      reasoning: "Common heroic archetype for fantasy stories.",
    });
  });

  it("POSTs to the suggest endpoint", async () => {
    let method = "";
    let path = "";
    server.use(
      http.post(
        "*/api/v1/novels/:novelId/kb/sessions/:sessionId/suggest/:fieldKey",
        async ({ request }) => {
          method = request.method;
          path = new URL(request.url).pathname;
          return HttpResponse.json({
            session: sessionResponse(),
            suggestion: {
              field_key: "description",
              suggestion: "x",
              reasoning: null,
              context_used: [],
            },
          });
        },
      ),
    );

    await suggestField("novel-1", "session-1", "description");

    expect(method).toBe("POST");
    expect(path).toContain("/novels/novel-1/kb/sessions/session-1/suggest/description");
  });

  it("surfaces the backend error on 400", async () => {
    server.use(
      http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/suggest/:fieldKey", async () =>
        HttpResponse.json({ detail: "Session is not active" }, { status: 400 }),
      ),
    );

    await expect(suggestField("novel-1", "session-1", "description")).rejects.toThrow(
      "Session is not active",
    );
  });

  it("rejects on abort signal", async () => {
    const controller = new AbortController();
    controller.abort();

    await expect(
      suggestField("novel-1", "session-1", "description", controller.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("requestInterview (REST)", () => {
  it("returns the real question from the JSON aggregate response", async () => {
    // Pins the wave-fix-4 emptiness class: the pre-fix SSE parser yielded zero
    // events on this plain-JSON body and resolved with an empty question.
    const result = await requestInterview("novel-1", "session-1");

    expect(result.question).toBe("Tell me about this character's greatest fear.");
    expect(result.target_field).toBe("background");
    expect(result.reasoning).toBe("Background is still empty; fears reveal backstory.");
  });

  it("surfaces the backend error on 400", async () => {
    server.use(
      http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/interview", async () =>
        HttpResponse.json({ detail: "Session is not active" }, { status: 400 }),
      ),
    );

    await expect(requestInterview("novel-1", "session-1")).rejects.toThrow("Session is not active");
  });

  it("rejects on abort signal", async () => {
    const controller = new AbortController();
    controller.abort();

    await expect(requestInterview("novel-1", "session-1", controller.signal)).rejects.toMatchObject(
      { name: "AbortError" },
    );
  });
});

describe("requestEnhance (REST)", () => {
  it("maps draft_entry to per-field enhancement results", async () => {
    const results = await requestEnhance("novel-1", "session-1");

    expect(results).toHaveLength(1);
    expect(results[0]).toEqual({
      field_key: "description",
      // The user's prior value travels back via the aggregate's session half.
      original: "A brave hero",
      suggested: "A brave and compassionate hero who always puts others before themselves.",
      reasoning: "Enhanced to show more depth and character traits.",
    });
  });

  it("skips non-string draft_entry values", async () => {
    server.use(
      http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/enhance", async () =>
        HttpResponse.json({
          session: sessionResponse(),
          enhancement: {
            draft_entry: { description: "Kept", tags: { nested: "object" }, aliases: ["a", "b"] },
            progress: 0.5,
            reasoning: "r",
            context_used: [],
          },
        }),
      ),
    );

    const results = await requestEnhance("novel-1", "session-1");

    expect(results.map((r) => r.field_key)).toEqual(["description"]);
  });

  it("surfaces the backend error on 400", async () => {
    server.use(
      http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/enhance", async () =>
        HttpResponse.json({ detail: "Session is not active" }, { status: 400 }),
      ),
    );

    await expect(requestEnhance("novel-1", "session-1")).rejects.toThrow("Session is not active");
  });

  it("rejects on abort signal", async () => {
    const controller = new AbortController();
    controller.abort();

    await expect(requestEnhance("novel-1", "session-1", controller.signal)).rejects.toMatchObject({
      name: "AbortError",
    });
  });
});
