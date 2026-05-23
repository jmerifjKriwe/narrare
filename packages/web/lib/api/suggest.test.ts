import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "./client";
import { createSseSuggestionFetcher } from "./suggest";

describe("createSseSuggestionFetcher", () => {
  const CHAPTER_ID = "chapter-42";

  beforeEach(() => {
    setAccessToken("");
  });

  // --- 1. Happy path: accumulates SSE chunks into final suggestion ----------

  it("should accumulate SSE chunks into final suggestion", async () => {
    // Arrange — capture request body and stream 3 SSE chunks
    let capturedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;

        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode('data: {"text":"The ","is_final":false}\n'),
            );
            controller.enqueue(
              new TextEncoder().encode('data: {"text":"old ","is_final":false}\n'),
            );
            controller.enqueue(
              new TextEncoder().encode('data: {"text":"house","is_final":true}\n'),
            );
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

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    // Act
    const result = await fetcher({
      textBefore: "Once upon a time, ",
      textAfter: " stood on the hill.",
      signal: new AbortController().signal,
    });

    // Assert — accumulated text matches concatenated chunks
    expect(result).toBe("The old house");

    // Assert — request body contains required fields
    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.text_before).toBe("Once upon a time, ");
    expect(capturedBody!.text_after).toBe(" stood on the hill.");
    expect(capturedBody!.language).toBe("en");
  });

  // --- 2. Abort signal: rejects with AbortError ------------------------------

  it("should reject with DOMException AbortError when signal is aborted", async () => {
    // Arrange — slow SSE stream that would run for ~100ms
    const abortController = new AbortController();

    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async () => {
        const stream = new ReadableStream({
          start(controller) {
            let count = 0;
            const interval = setInterval(() => {
              if (count >= 10) {
                clearInterval(interval);
                controller.close();
                return;
              }
              controller.enqueue(
                new TextEncoder().encode(`data: {"text":"chunk${count}","is_final":false}\n`),
              );
              count++;
            }, 10);
          },
        });

        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    // Act — abort after 50ms, before stream completes
    setTimeout(() => abortController.abort(), 50);

    let caughtError: unknown;
    try {
      await fetcher({
        textBefore: "test",
        textAfter: "",
        signal: abortController.signal,
      });
    } catch (error) {
      caughtError = error;
    }

    // Assert — rejected with DOMException named AbortError
    expect(caughtError).toBeInstanceOf(DOMException);
    expect((caughtError as DOMException).name).toBe("AbortError");
    expect((caughtError as DOMException).message).toBe("Aborted");
  });

  // --- 3. HTTP error: rejects with error -------------------------------------

  it("should reject with error containing status on HTTP error", async () => {
    // Arrange — server returns 500
    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async () => {
        return HttpResponse.json({ detail: "Internal Server Error" }, { status: 500 });
      }),
    );

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    // Act & Assert
    await expect(
      fetcher({
        textBefore: "test",
        textAfter: "",
        signal: new AbortController().signal,
      }),
    ).rejects.toThrow("HTTP 500");
  });

  // --- 4. Empty response: resolves with empty string -------------------------

  it("should resolve with empty string when SSE sends [DONE] immediately", async () => {
    // Arrange — stream with [DONE] and no text chunks
    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async () => {
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });

        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    // Act
    const result = await fetcher({
      textBefore: "test",
      textAfter: "",
      signal: new AbortController().signal,
    });

    // Assert
    expect(result).toBe("");
  });

  // --- 5. Language parameter: passed in request body -------------------------

  it("should pass custom language parameter in request body", async () => {
    // Arrange
    let capturedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;

        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });

        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    // Create fetcher with German language
    const fetcher = createSseSuggestionFetcher(CHAPTER_ID, "de");

    // Act
    await fetcher({
      textBefore: "Es war einmal ",
      textAfter: "",
      signal: new AbortController().signal,
    });

    // Assert — language field is "de"
    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.language).toBe("de");
  });

  // --- 6. Missing text_after: not sent when empty ----------------------------

  it("should omit text_after from request body when textAfter is empty", async () => {
    // Arrange
    let capturedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;

        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });

        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    // Act — textAfter is empty string
    await fetcher({
      textBefore: "Hello",
      textAfter: "",
      signal: new AbortController().signal,
    });

    // Assert — text_after is undefined (not in JSON body)
    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.text_after).toBeUndefined();
  });
});
