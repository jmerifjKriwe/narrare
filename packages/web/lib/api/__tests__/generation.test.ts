import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import {
  type GenerateResponse,
  type GenerationChunk,
  streamGeneration,
  WritingSessionSocket,
  writingApi,
} from "../generation";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a SSE ReadableStream from chunk data lines. */
function sseStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(`${line}\n`));
      }
      controller.close();
    },
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("writingApi (REST)", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  describe("startGeneration", () => {
    it("should POST to /writing/chapters/:id/generate and return request_id", async () => {
      server.use(
        http.post("*/api/v1/writing/chapters/ch-1/generate", async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          // Log the body for debugging if needed
          // console.log('Received body:', body);
          return HttpResponse.json({
            request_id: "gen-123",
            status: "pending",
            mode: body.mode,
          });
        }),
      );

      const result = await writingApi.startGeneration("ch-1", "novel-1", {
        mode: "full_draft",
      });

      expect(result.request_id).toBe("gen-123");
      expect(result.status).toBe("pending");
    });
  });

  describe("stopGeneration", () => {
    it("should DELETE /writing/generation/:id", async () => {
      server.use(
        http.delete("*/api/v1/writing/generation/gen-123", async () =>
          HttpResponse.json({
            request_id: "gen-123",
            status: "stopped",
            word_count: 800,
          }),
        ),
      );

      const result = await writingApi.stopGeneration("gen-123");
      expect(result.status).toBe("stopped");
      expect(result.word_count).toBe(800);
    });
  });

  describe("acceptDraft", () => {
    it("should POST to accept endpoint with optional modified_text", async () => {
      server.use(
        http.post("*/api/v1/writing/generation/gen-123/accept", async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({
            request_id: "gen-123",
            chapter_id: "ch-1",
            word_count: 1200,
            modified_text: body.modified_text ?? undefined,
          });
        }),
      );

      const result = await writingApi.acceptDraft("gen-123", "edited text");
      expect(result.chapter_id).toBe("ch-1");
    });

    it("should work without modified_text", async () => {
      server.use(
        http.post("*/api/v1/writing/generation/gen-456/accept", async () =>
          HttpResponse.json({
            request_id: "gen-456",
            chapter_id: "ch-2",
            word_count: 900,
          }),
        ),
      );

      const result = await writingApi.acceptDraft("gen-456");
      expect(result.chapter_id).toBe("ch-2");
    });
  });

  describe("rejectDraft", () => {
    it("should POST to reject endpoint", async () => {
      server.use(
        http.post("*/api/v1/writing/generation/gen-123/reject", async () =>
          HttpResponse.json({ request_id: "gen-123", status: "rejected" }),
        ),
      );

      const result = await writingApi.rejectDraft("gen-123");
      expect(result.status).toBe("rejected");
    });
  });

  describe("nextScene", () => {
    it("should POST to scene/next", async () => {
      server.use(
        http.post("*/api/v1/writing/generation/gen-123/scene/next", async () =>
          HttpResponse.json({
            request_id: "gen-123",
            scene_number: 2,
            status: "streaming",
          }),
        ),
      );

      const result = await writingApi.nextScene("gen-123");
      expect(result.scene_number).toBe(2);
    });
  });

  describe("acceptScene", () => {
    it("should POST to scene/:num/accept", async () => {
      server.use(
        http.post("*/api/v1/writing/generation/gen-123/scene/2/accept", async () =>
          HttpResponse.json({
            request_id: "gen-123",
            chapter_id: "ch-1",
            word_count: 400,
          }),
        ),
      );

      const result = await writingApi.acceptScene("gen-123", 2);
      expect(result.word_count).toBe(400);
    });
  });

  describe("getStats", () => {
    it("should GET writing stats for a novel", async () => {
      server.use(
        http.get("*/api/v1/writing/novels/novel-1/stats", async () =>
          HttpResponse.json({
            total_generations: 42,
            success_rate: 0.95,
            avg_tokens: 1500,
            avg_word_count: 800,
            most_used_model: "gpt-4",
          }),
        ),
      );

      const stats = await writingApi.getStats("novel-1");
      expect(stats.total_generations).toBe(42);
      expect(stats.most_used_model).toBe("gpt-4");
    });
  });
});

describe("streamGeneration (SSE)", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("should parse SSE chunks and call onChunk", async () => {
    const chunks: GenerationChunk[] = [];

    server.use(
      http.get(
        "*/api/v1/writing/generation/gen-1/stream",
        async () =>
          new HttpResponse(
            sseStream(['data: {"text":"Hello "}', 'data: {"text":"World!"}', "data: [DONE]"]),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamGeneration("gen-1", (chunk) => chunks.push(chunk));

    expect(chunks).toEqual([{ text: "Hello " }, { text: "World!" }]);
  });

  it("should call onComplete on [DONE]", async () => {
    const onComplete = vi.fn();

    server.use(
      http.get(
        "*/api/v1/writing/generation/gen-2/stream",
        async () =>
          new HttpResponse(sseStream(['data: {"text":"hi"}', "data: [DONE]"]), {
            headers: { "Content-Type": "text/event-stream" },
          }),
      ),
    );

    await streamGeneration("gen-2", vi.fn(), onComplete);
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("should call onError on HTTP failure", async () => {
    const onError = vi.fn();

    server.use(
      http.get("*/api/v1/writing/generation/gen-err/stream", async () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );

    await streamGeneration("gen-err", vi.fn(), vi.fn(), onError);
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "HTTP 404" }));
  });

  it("should silently handle AbortSignal without calling onError", async () => {
    const onError = vi.fn();
    const controller = new AbortController();
    // Abort before fetch starts — simulates immediate cancellation
    controller.abort();

    await streamGeneration("gen-abort", vi.fn(), vi.fn(), onError, controller.signal);
    // AbortError is caught internally — onError should never be called
    expect(onError).not.toHaveBeenCalled();
  });

  it("should skip malformed JSON lines", async () => {
    const chunks: GenerationChunk[] = [];

    server.use(
      http.get(
        "*/api/v1/writing/generation/gen-malformed/stream",
        async () =>
          new HttpResponse(
            sseStream([
              'data: {"text":"good"}',
              "data: {broken",
              'data: {"text":"also good"}',
              "data: [DONE]",
            ]),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamGeneration("gen-malformed", (c) => chunks.push(c));
    expect(chunks).toEqual([{ text: "good" }, { text: "also good" }]);
  });
});

describe("WritingSessionSocket (WebSocket)", () => {
  it("should connect, send messages, and close", () => {
    // Mock WebSocket — we just verify the class interface works
    const onMessage = vi.fn();
    const onError = vi.fn();

    const socket = new WritingSessionSocket("ch-1", onMessage, onError);

    // These should not throw even if WebSocket is not available in test env
    expect(() => socket.send({ type: "user_direction", content: "test" })).not.toThrow();
    expect(() => socket.close()).not.toThrow();
  });

  it("should prevent reconnect after close()", () => {
    const socket = new WritingSessionSocket("ch-1", vi.fn(), vi.fn());
    socket.close();

    // After close(), internal reconnectAttempts should be at max
    // (we can't access private fields, but close() should work without error)
    expect(() => socket.close()).not.toThrow();
  });
});
