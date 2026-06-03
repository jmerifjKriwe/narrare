import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setAccessToken } from "@/lib/api/client";
import { streamCoAuthor } from "@/lib/api/coauthor";
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
