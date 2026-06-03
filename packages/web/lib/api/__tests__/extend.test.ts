import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setAccessToken } from "@/lib/api/client";
import { streamExtend } from "@/lib/api/generation";
import { server } from "@/mocks/server";

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
// Tests: streamExtend
// ---------------------------------------------------------------------------

describe("streamExtend", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("POSTs to /extend endpoint and streams text chunks", async () => {
    const chunks: string[] = [];
    let completed = false;
    let receivedRequestId = "";

    server.use(
      http.post("*/api/v1/writing/chapters/chapter-1/extend", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.text_before).toBe("Some text");
        expect(body.length).toBe("medium");

        return new HttpResponse(
          sseStream([
            'data: {"type":"request_info","request_id":"ext-1"}',
            'data: {"text":"The old "}',
            'data: {"text":"house stood."}',
            "data: [DONE]",
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }),
    );

    await streamExtend(
      "chapter-1",
      "novel-1",
      { text_before: "Some text", length: "medium" },
      {
        onRequestInfo: (id) => {
          receivedRequestId = id;
        },
        onChunk: (text) => chunks.push(text),
        onComplete: () => {
          completed = true;
        },
        onError: () => {},
      },
    );

    expect(chunks).toEqual(["The old ", "house stood."]);
    expect(completed).toBe(true);
    expect(receivedRequestId).toBe("ext-1");
  });

  it("calls onError on HTTP failure", async () => {
    const errors: Error[] = [];

    server.use(
      http.post("*/api/v1/writing/chapters/ch-err/extend", async () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );

    await streamExtend(
      "ch-err",
      "novel-1",
      { text_before: "Some text" },
      {
        onChunk: () => {},
        onError: (err) => errors.push(err),
      },
    );

    expect(errors).toHaveLength(1);
    expect(errors[0].message).toBe("HTTP 404");
  });

  it("sends correct request body with all fields", async () => {
    let receivedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/chapter-2/extend", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return new HttpResponse(sseStream(["data: [DONE]"]), {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    await streamExtend(
      "chapter-2",
      "novel-1",
      {
        text_before: "Hello world",
        text_after: "Goodbye",
        length: "long",
        tone: "dramatic",
        language: "en",
      },
      { onChunk: () => {}, onComplete: () => {} },
    );

    expect(receivedBody).not.toBeNull();
    expect(receivedBody!.text_before).toBe("Hello world");
    expect(receivedBody!.text_after).toBe("Goodbye");
    expect(receivedBody!.length).toBe("long");
    expect(receivedBody!.tone).toBe("dramatic");
    expect(receivedBody!.language).toBe("en");
  });

  it("skips malformed JSON lines", async () => {
    const chunks: string[] = [];
    const onError = vi.fn();

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-malformed/extend",
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

    await streamExtend(
      "ch-malformed",
      "novel-1",
      { text_before: "Some text" },
      { onChunk: (text) => chunks.push(text), onError },
    );

    expect(chunks).toEqual(["good", "also good"]);
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ kind: "parse" }));
  });

  it("preserves partial chunks when a network error occurs", async () => {
    const chunks: string[] = [];
    const onError = vi.fn();

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-partial/extend",
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

    await streamExtend(
      "ch-partial",
      "novel-1",
      { text_before: "Some text" },
      { onChunk: (text) => chunks.push(text), onError },
    );

    expect(chunks).toEqual(["partial"]);
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "connection lost" }));
  });
});
