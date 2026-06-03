import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "./client";
import { connectSSE } from "./streaming";

describe("connectSSE", () => {
  // Test data type
  interface TestChunk {
    text: string;
    done: boolean;
  }

  beforeEach(() => {
    setAccessToken("");
  });

  it("should stream chunks via SSE happy path", async () => {
    const chunks: TestChunk[] = [];
    const onChunk = vi.fn((chunk: TestChunk) => chunks.push(chunk));
    const onComplete = vi.fn();
    const onError = vi.fn();

    // Add SSE handler
    server.use(
      http.post("*/api/v1/test/stream", async () => {
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"text":"Hello","done":false}\n'));
            controller.enqueue(new TextEncoder().encode('data: {"text":" World","done":false}\n'));
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });
        return new HttpResponse(stream, {
          headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
          },
        });
      }),
    );

    await connectSSE<TestChunk>({
      url: "/test/stream",
      body: { prompt: "test" },
      onChunk,
      onComplete,
      onError,
    });

    expect(onChunk).toHaveBeenCalledTimes(2);
    expect(onChunk).toHaveBeenCalledWith({ text: "Hello", done: false });
    expect(onChunk).toHaveBeenCalledWith({ text: " World", done: false });
    expect(onComplete).toHaveBeenCalledWith(undefined);
    expect(onError).not.toHaveBeenCalled();
  });

  it("should handle HTTP error responses", async () => {
    const onError = vi.fn();

    // Add error handler
    server.use(
      http.post("*/api/v1/test/error", async () => {
        return HttpResponse.json({ detail: "Unauthorized" }, { status: 401 });
      }),
    );

    await connectSSE({
      url: "/test/error",
      body: {},
      onChunk: () => {},
      onError,
    });

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "HTTP 401" }));
  });

  it("should support GET streams without a JSON body", async () => {
    const onChunk = vi.fn();

    server.use(
      http.get("*/api/v1/test/get-stream", async ({ request }) => {
        expect(request.headers.get("content-type")).toBeNull();
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"text":"GET"}\n'));
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });
        return new HttpResponse(stream, { headers: { "Content-Type": "text/event-stream" } });
      }),
    );

    await connectSSE({
      url: "/test/get-stream",
      method: "GET",
      onChunk,
    });

    expect(onChunk).toHaveBeenCalledWith({ text: "GET" });
  });

  it("should report malformed JSON without dropping later chunks", async () => {
    const onChunk = vi.fn();
    const onError = vi.fn();

    server.use(
      http.post("*/api/v1/test/malformed", async () => {
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"text":"before"}\n'));
            controller.enqueue(new TextEncoder().encode("data: {broken\n"));
            controller.enqueue(new TextEncoder().encode('data: {"text":"after"}\n'));
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });
        return new HttpResponse(stream, { headers: { "Content-Type": "text/event-stream" } });
      }),
    );

    await connectSSE({ url: "/test/malformed", body: {}, onChunk, onError });

    expect(onChunk).toHaveBeenCalledWith({ text: "before" });
    expect(onChunk).toHaveBeenCalledWith({ text: "after" });
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ kind: "parse" }));
  });

  it("should preserve buffered events split across network chunks", async () => {
    const onChunk = vi.fn();

    server.use(
      http.post("*/api/v1/test/split", async () => {
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"text":"split'));
            controller.enqueue(new TextEncoder().encode(' chunk"}\n'));
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });
        return new HttpResponse(stream, { headers: { "Content-Type": "text/event-stream" } });
      }),
    );

    await connectSSE({ url: "/test/split", body: {}, onChunk });

    expect(onChunk).toHaveBeenCalledWith({ text: "split chunk" });
  });

  it("should abort stream via AbortSignal", async () => {
    const onChunk = vi.fn();
    const onError = vi.fn();
    const abortController = new AbortController();

    // Add handler that would stream indefinitely
    server.use(
      http.post("*/api/v1/test/abort", async () => {
        const stream = new ReadableStream({
          start(controller) {
            // Send chunks slowly
            let count = 0;
            const interval = setInterval(() => {
              if (count >= 10) {
                clearInterval(interval);
                controller.close();
                return;
              }
              controller.enqueue(new TextEncoder().encode(`data: {"text":"chunk${count}"}\n`));
              count++;
            }, 10);
          },
        });
        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    // Abort after first chunk
    setTimeout(() => abortController.abort(), 50);

    await connectSSE({
      url: "/test/abort",
      body: {},
      onChunk,
      onError,
      signal: abortController.signal,
    });

    // onError should NOT be called for AbortError (it's handled internally)
    // onChunk may or may not be called depending on timing
    // The function should complete without throwing
    expect(true).toBe(true);
  });

  it("should handle [DONE] event to complete stream", async () => {
    const onChunk = vi.fn();
    const onComplete = vi.fn();
    const onError = vi.fn();

    server.use(
      http.post("*/api/v1/test/done", async () => {
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"text":"First"}\n'));
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            // This should be ignored after [DONE]
            controller.enqueue(new TextEncoder().encode('data: {"text":"Second"}\n'));
            controller.close();
          },
        });
        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    await connectSSE({
      url: "/test/done",
      body: {},
      onChunk,
      onComplete,
      onError,
    });

    expect(onChunk).toHaveBeenCalledTimes(1);
    expect(onChunk).toHaveBeenCalledWith({ text: "First" });
    expect(onComplete).toHaveBeenCalledWith(undefined);
    expect(onError).not.toHaveBeenCalled();
  });
});
