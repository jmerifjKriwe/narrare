import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setAccessToken } from "@/lib/api/client";
import {
  type ApplyChangesRequest,
  applyChanges,
  type CoAuthorFeedbackRequest,
  recordFeedback,
  streamCoAuthor,
} from "@/lib/api/coauthor";
import { server } from "@/mocks/server";

function sseStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const line of lines) controller.enqueue(encoder.encode(`${line}\n`));
      controller.close();
    },
  });
}

describe("streamCoAuthor", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("calls onContextMeta when a context_meta event is received", async () => {
    const chunks: string[] = [];
    const onContextMeta = vi.fn();
    const onComplete = vi.fn();

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-meta/co-author",
        async () =>
          new HttpResponse(
            sseStream([
              'data: {"type":"context_meta","suggested_characters":3,"tone":"formal"}',
              'data: {"text":"improved text","is_final":true}',
              "data: [DONE]",
            ]),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamCoAuthor(
      "ch-meta",
      "novel-1",
      { selection_text: "Original", focus: ["sentence"] },
      { onChunk: (text) => chunks.push(text), onComplete, onContextMeta },
    );

    expect(onContextMeta).toHaveBeenCalledOnce();
    expect(chunks).toEqual(["improved text"]);
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("streams chunks and emits final revision", async () => {
    const chunks: string[] = [];
    const onComplete = vi.fn();

    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/co-author", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.selection_text).toBe("Original");
        return new HttpResponse(
          sseStream([
            'data: {"text":"Better "}',
            'data: {"text":"sentence","is_final":true,"changes":[{"id":"c1","change_type":"sentence","original_text":"Original","revised_text":"Better sentence","index":0}],"reasoning":"clearer","request_id":"req-1"}',
            "data: [DONE]",
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }),
    );

    await streamCoAuthor(
      "ch-1",
      "novel-1",
      { selection_text: "Original", focus: ["sentence"] },
      { onChunk: (text) => chunks.push(text), onComplete },
    );

    expect(chunks).toEqual(["Better ", "sentence"]);
    expect(onComplete).toHaveBeenCalledWith({
      original: "Original",
      revised: "sentence",
      changes: [
        {
          id: "c1",
          change_type: "sentence",
          original_text: "Original",
          revised_text: "Better sentence",
          index: 0,
        },
      ],
      reasoning: "clearer",
      request_id: "req-1",
    });
  });

  it("reports parse errors without dropping later chunks", async () => {
    const chunks: string[] = [];
    const onError = vi.fn();

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-mal/co-author",
        async () =>
          new HttpResponse(
            sseStream([
              'data: {"text":"good"}',
              "data: {broken",
              'data: {"text":"again"}',
              "data: [DONE]",
            ]),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamCoAuthor(
      "ch-mal",
      "novel-1",
      { selection_text: "Original", focus: ["sentence"] },
      { onChunk: (text) => chunks.push(text), onComplete: vi.fn(), onError },
    );

    expect(chunks).toEqual(["good", "again"]);
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ kind: "parse" }));
  });

  it("preserves partial revision when the stream fails", async () => {
    const chunks: string[] = [];
    const onError = vi.fn();
    const onComplete = vi.fn();

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-partial/co-author",
        async () =>
          new HttpResponse(
            new ReadableStream({
              start(controller) {
                controller.enqueue(new TextEncoder().encode('data: {"text":"partial"}\n'));
                setTimeout(() => controller.error(new Error("connection lost")), 0);
              },
            }),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamCoAuthor(
      "ch-partial",
      "novel-1",
      { selection_text: "Original", focus: ["sentence"] },
      { onChunk: (text) => chunks.push(text), onComplete, onError },
    );

    expect(chunks).toEqual(["partial"]);
    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "connection lost" }));
  });
});

describe("applyChanges", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  const applyRequest: ApplyChangesRequest = {
    request_id: "req-1",
    original: "Original text",
    accepted: [{ original_text: "dull", revised_text: "vivid" }],
    rejected: [{ original_text: "boring", revised_text: "exciting" }],
  };

  it("POSTs accepted/rejected changes and returns updated chapter", async () => {
    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/co-author/apply", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.request_id).toBe("req-1");
        expect(body.accepted).toHaveLength(1);
        expect(body.rejected).toHaveLength(1);
        return HttpResponse.json({ id: "ch-1", content: "Updated content" });
      }),
    );

    const result = await applyChanges("ch-1", "novel-1", applyRequest);
    expect(result.id).toBe("ch-1");
    expect(result.content).toBe("Updated content");
  });

  it("throws on HTTP error", async () => {
    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/co-author/apply", () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );

    await expect(applyChanges("ch-1", "novel-1", applyRequest)).rejects.toThrow("HTTP 404");
  });

  it("works without access token (no Authorization header)", async () => {
    // Clear any token set by beforeEach
    setAccessToken("");

    let capturedAuth = "";
    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/co-author/apply", async ({ request }) => {
        capturedAuth = request.headers.get("Authorization") ?? "";
        return HttpResponse.json({ id: "ch-1", content: "Content" });
      }),
    );

    const result = await applyChanges("ch-1", "novel-1", applyRequest);
    expect(capturedAuth).toBe("");
    expect(result.content).toBe("Content");
  });
});

describe("recordFeedback", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  const feedbackRequest: CoAuthorFeedbackRequest = {
    request_id: "req-1",
    feedback: [
      { change_id: "c1", action: "accepted", focus: "sentence", original: "old", revised: "new" },
    ],
  };

  it("POSTs feedback and succeeds silently", async () => {
    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/co-author/feedback", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.request_id).toBe("req-1");
        expect(body.feedback).toHaveLength(1);
        return HttpResponse.json({});
      }),
    );

    await expect(recordFeedback("ch-1", "novel-1", feedbackRequest)).resolves.toBeUndefined();
  });

  it("throws on HTTP error", async () => {
    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/co-author/feedback", () =>
        HttpResponse.json({ detail: "Bad Request" }, { status: 400 }),
      ),
    );

    await expect(recordFeedback("ch-1", "novel-1", feedbackRequest)).rejects.toThrow("HTTP 400");
  });

  it("works without access token", async () => {
    setAccessToken("");

    let capturedAuth = "";
    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/co-author/feedback", async ({ request }) => {
        capturedAuth = request.headers.get("Authorization") ?? "";
        return HttpResponse.json({});
      }),
    );

    await recordFeedback("ch-1", "novel-1", feedbackRequest);
    expect(capturedAuth).toBe("");
  });
});
