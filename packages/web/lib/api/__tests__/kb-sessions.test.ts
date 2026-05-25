/**
 * KB Sessions API client tests.
 *
 * Tests for REST operations and SSE operations.
 * REST: createSession, getSession, answerField, completeSession, abandonSession
 * SSE: suggestField, requestInterview, requestEnhance (with mocked connectSSE)
 */

import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { kbSessionApi, requestEnhance, requestInterview, suggestField } from "../kb-sessions";

// ---------------------------------------------------------------------------
// Mock connectSSE for SSE operation tests
// ---------------------------------------------------------------------------

vi.mock("../streaming", () => ({
  connectSSE: vi.fn(),
}));

// Need to import the mocked module to set up mock implementations
import { connectSSE } from "../streaming";

const mockConnectSSE = connectSSE as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clearMockConnectSSE() {
  mockConnectSSE.mockReset();
}

function mockSuggestFieldSSE(textChunks: { type: string; text: string }[]) {
  mockConnectSSE.mockImplementation(
    ({
      onChunk,
      onComplete,
      onError,
    }: {
      onChunk: (c: { type: string; text: string }) => void;
      onComplete: () => void;
      onError: (e: Error) => void;
    }) => {
      try {
        for (const chunk of textChunks) {
          onChunk(chunk);
        }
        onComplete();
      } catch (e) {
        onError(e instanceof Error ? e : new Error(String(e)));
      }
    },
  );
}

function mockInterviewSSE(textChunks: { type: string; text: string }[]) {
  mockConnectSSE.mockImplementation(
    ({
      onChunk,
      onComplete,
    }: {
      onChunk: (c: { type: string; text: string }) => void;
      onComplete: () => void;
    }) => {
      for (const chunk of textChunks) {
        onChunk(chunk);
      }
      onComplete();
    },
  );
}

function mockEnhanceSSE(textChunks: { type: string; text: string }[]) {
  mockConnectSSE.mockImplementation(
    ({
      onChunk,
      onComplete,
    }: {
      onChunk: (c: { type: string; text: string }) => void;
      onComplete: () => void;
    }) => {
      for (const chunk of textChunks) {
        onChunk(chunk);
      }
      onComplete();
    },
  );
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
            {
              id: "custom",
              novel_id: "novel-1",
              user_id: "u1",
              entity_type: body.entity_type as string,
              status: "active",
              fields: [],
              context_entries: [],
              created_at: "",
              updated_at: "",
            },
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
    it("POST /novels/:novelId/kb/sessions/:sessionId/complete", async () => {
      const result = await kbSessionApi.completeSession("novel-1", "session-1");

      expect(result.session.status).toBe("complete");
      expect(result.entry_id).toBeDefined();
    });

    it("throws on server error", async () => {
      server.use(
        http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/complete", async () =>
          HttpResponse.json({ detail: "Session already completed" }, { status: 409 }),
        ),
      );

      await expect(kbSessionApi.completeSession("novel-1", "session-1")).rejects.toThrow(
        "Session already completed",
      );
    });
  });

  describe("abandonSession", () => {
    it("DELETE /novels/:novelId/kb/sessions/:sessionId", async () => {
      const result = await kbSessionApi.abandonSession("novel-1", "session-1");

      expect(result).toBeUndefined();
    });
  });
});

describe("suggestField (SSE)", () => {
  beforeEach(() => {
    clearMockConnectSSE();
  });

  it("accumulates text chunks and returns suggestion", async () => {
    mockSuggestFieldSSE([
      { type: "text", text: "A brave " },
      { type: "text", text: "adventurer" },
      { type: "reasoning", text: "Common archetype" },
    ]);

    const result = await suggestField("novel-1", "session-1", "description");

    expect(result.field_key).toBe("description");
    expect(result.suggestion).toBe("A brave adventurer");
    expect(result.reasoning).toBe("Common archetype");
  });

  it("handles reasoning chunks correctly", async () => {
    mockSuggestFieldSSE([
      { type: "text", text: "A mysterious stranger" },
      { type: "reasoning", text: "Reason 1. " },
      { type: "reasoning", text: "Reason 2." },
    ]);

    const result = await suggestField("novel-1", "session-1", "background");

    expect(result.suggestion).toBe("A mysterious stranger");
    expect(result.reasoning).toBe("Reason 1. Reason 2.");
  });

  it("rejects on SSE error", async () => {
    mockConnectSSE.mockImplementation(({ onError }: { onError: (e: Error) => void }) => {
      onError(new Error("SSE connection failed"));
    });

    await expect(suggestField("novel-1", "session-1", "description")).rejects.toThrow(
      "SSE connection failed",
    );
  });

  it("rejects on abort signal", async () => {
    const controller = new AbortController();
    controller.abort();

    await expect(
      suggestField("novel-1", "session-1", "description", controller.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
  });

  it("handles empty suggestion gracefully", async () => {
    mockSuggestFieldSSE([]);

    const result = await suggestField("novel-1", "session-1", "empty_field");

    expect(result.field_key).toBe("empty_field");
    expect(result.suggestion).toBe("");
    expect(result.reasoning).toBe("");
  });

  it("passes novelId, sessionId, fieldKey to connectSSE URL", async () => {
    mockSuggestFieldSSE([{ type: "text", text: "test" }]);

    await suggestField("novel-1", "session-1", "description");

    expect(mockConnectSSE).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/novels/novel-1/kb/sessions/session-1/suggest/description",
      }),
    );
  });
});

describe("requestInterview (SSE)", () => {
  beforeEach(() => {
    clearMockConnectSSE();
  });

  it("accumulates question and identifies target field", async () => {
    mockInterviewSSE([
      { type: "meta", text: "field:name" },
      { type: "text", text: "What is this " },
      { type: "text", text: "character's name?" },
    ]);

    const result = await requestInterview("novel-1", "session-1");

    expect(result.question).toBe("What is this character's name?");
    expect(result.target_field).toBe("name");
  });

  it("returns empty target field when no meta", async () => {
    mockInterviewSSE([{ type: "text", text: "Tell me about the character." }]);

    const result = await requestInterview("novel-1", "session-1");

    expect(result.question).toBe("Tell me about the character.");
    expect(result.target_field).toBe("");
  });

  it("rejects on SSE error", async () => {
    mockConnectSSE.mockImplementation(({ onError }: { onError: (e: Error) => void }) => {
      onError(new Error("Interview SSE failed"));
    });

    await expect(requestInterview("novel-1", "session-1")).rejects.toThrow("Interview SSE failed");
  });

  it("rejects on abort signal", async () => {
    const controller = new AbortController();
    controller.abort();

    await expect(requestInterview("novel-1", "session-1", controller.signal)).rejects.toMatchObject(
      { name: "AbortError" },
    );
  });

  it("passes correct URL to connectSSE", async () => {
    mockInterviewSSE([{ type: "text", text: "test" }]);

    await requestInterview("novel-1", "session-1");

    expect(mockConnectSSE).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/novels/novel-1/kb/sessions/session-1/interview",
      }),
    );
  });
});

describe("requestEnhance (SSE)", () => {
  beforeEach(() => {
    clearMockConnectSSE();
  });

  it("accumulates multiple enhancements from SSE chunks", async () => {
    mockEnhanceSSE([
      { type: "meta", text: "field:description" },
      { type: "original", text: "A brave hero" },
      { type: "text", text: "A brave and selfless hero" },
      { type: "reasoning", text: "Added depth" },
      { type: "meta", text: "field:name" },
      { type: "original", text: "Test" },
      { type: "text", text: "Sir Aldric" },
      { type: "reasoning", text: "More evocative" },
    ]);

    const results = await requestEnhance("novel-1", "session-1");

    expect(results).toHaveLength(2);
    expect(results[0].field_key).toBe("description");
    expect(results[0].original).toBe("A brave hero");
    expect(results[0].suggested).toBe("A brave and selfless hero");
    expect(results[0].reasoning).toBe("Added depth");

    expect(results[1].field_key).toBe("name");
    expect(results[1].original).toBe("Test");
    expect(results[1].suggested).toBe("Sir Aldric");
    expect(results[1].reasoning).toBe("More evocative");
  });

  it("handles single enhancement", async () => {
    mockEnhanceSSE([
      { type: "meta", text: "field:description" },
      { type: "original", text: "Old" },
      { type: "text", text: "New" },
      { type: "reasoning", text: "Better" },
    ]);

    const results = await requestEnhance("novel-1", "session-1");

    expect(results).toHaveLength(1);
    expect(results[0].field_key).toBe("description");
    expect(results[0].suggested).toBe("New");
  });

  it("handles empty enhancements", async () => {
    mockEnhanceSSE([]);

    const results = await requestEnhance("novel-1", "session-1");
    expect(results).toHaveLength(0);
  });

  it("rejects on SSE error", async () => {
    mockConnectSSE.mockImplementation(({ onError }: { onError: (e: Error) => void }) => {
      onError(new Error("Enhance SSE failed"));
    });

    await expect(requestEnhance("novel-1", "session-1")).rejects.toThrow("Enhance SSE failed");
  });

  it("rejects on abort signal", async () => {
    const controller = new AbortController();
    controller.abort();

    await expect(requestEnhance("novel-1", "session-1", controller.signal)).rejects.toMatchObject({
      name: "AbortError",
    });
  });

  it("passes correct URL to connectSSE", async () => {
    mockEnhanceSSE([
      { type: "meta", text: "field:test" },
      { type: "text", text: "x" },
    ]);

    await requestEnhance("novel-1", "session-1");

    expect(mockConnectSSE).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/novels/novel-1/kb/sessions/session-1/enhance",
      }),
    );
  });
});
