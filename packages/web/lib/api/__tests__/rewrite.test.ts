import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setAccessToken } from "@/lib/api/client";
import { parseAlternatives, streamRewrite } from "@/lib/api/generation";
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
// Tests: parseAlternatives
// ---------------------------------------------------------------------------

describe("parseAlternatives", () => {
  it("parses well-formed multi-alternative response", () => {
    const text =
      '<alternative label="Tone shift">The dark clouds gathered.</alternative>\n<alternative label="Style change">Stormy weather approached.</alternative>';

    const result = parseAlternatives(text);

    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ label: "Tone shift", text: "The dark clouds gathered." });
    expect(result[1]).toEqual({ label: "Style change", text: "Stormy weather approached." });
  });

  it("parses single alternative", () => {
    const text = '<alternative label="Rewritten">Better text here.</alternative>';

    const result = parseAlternatives(text);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ label: "Rewritten", text: "Better text here." });
  });

  it("falls back to single alternative when no tags found", () => {
    const text = "Just plain text with no tags at all.";

    const result = parseAlternatives(text);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      label: "Rewritten text",
      text: "Just plain text with no tags at all.",
    });
  });

  it("handles empty text", () => {
    const result = parseAlternatives("");

    expect(result).toHaveLength(0);
  });

  it("handles tag-like content not at line boundary", () => {
    // <alternative within text should NOT be recognized as a tag opener
    const text = 'Some text <alternative label="foo"> more text';

    const result = parseAlternatives(text);

    // Falls back to single alternative since no valid boundary tags found
    expect(result).toHaveLength(1);
    expect(result[0].label).toBe("Rewritten text");
  });

  it("recognizes opening tag at start of text (valid boundary)", () => {
    const text = '<alternative label="First">Hello world</alternative>';

    const result = parseAlternatives(text);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ label: "First", text: "Hello world" });
  });

  it("recognizes opening tag after closing tag (valid boundary)", () => {
    const text =
      '<alternative label="A">First</alternative><alternative label="B">Second</alternative>';

    const result = parseAlternatives(text);

    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ label: "A", text: "First" });
    expect(result[1]).toEqual({ label: "B", text: "Second" });
  });

  it("handles incomplete alternative (no closing tag)", () => {
    const text = '<alternative label="Incomplete">Some text without closing';

    const result = parseAlternatives(text);

    // Falls back since no complete alternative found
    expect(result).toHaveLength(1);
    expect(result[0].label).toBe("Rewritten text");
  });

  it("handles alternative with empty label", () => {
    const text = '<alternative label="">Some content</alternative>';

    const result = parseAlternatives(text);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ label: "", text: "Some content" });
  });
});

// ---------------------------------------------------------------------------
// Tests: streamRewrite
// ---------------------------------------------------------------------------

describe("streamRewrite", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("POSTs to /rewrite endpoint and streams alternatives", async () => {
    const alternatives: { label: string; text: string }[] = [];
    let finalCount = 0;

    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/rewrite", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.selection_text).toBe("Some selected text");
        expect(body.mode).toBe("tone");

        return new HttpResponse(
          sseStream([
            'data: {"type":"request_info","request_id":"rw-1"}',
            'data: {"text":"<alternative label=\\"Tone shift\\">Darker text.</alternative>\\n<alternative label=\\"Style\\">Brighter text.</alternative>"}',
            "data: [DONE]",
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }),
    );

    await streamRewrite(
      "ch-1",
      "novel-1",
      {
        selection_text: "Some selected text",
        mode: "tone",
        options: { option: "more dramatic" },
        count: 2,
      },
      {
        onAlternative: (label, text) => alternatives.push({ label, text }),
        onAlternativeFinal: (count) => {
          finalCount = count;
        },
        onError: () => {},
      },
    );

    expect(alternatives).toHaveLength(2);
    expect(alternatives[0]).toEqual({ label: "Tone shift", text: "Darker text." });
    expect(alternatives[1]).toEqual({ label: "Style", text: "Brighter text." });
    expect(finalCount).toBe(2);
  });

  it("calls onError on HTTP failure", async () => {
    const errors: Error[] = [];

    server.use(
      http.post("*/api/v1/writing/chapters/ch-err/rewrite", async () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );

    await streamRewrite(
      "ch-err",
      "novel-1",
      { selection_text: "text", mode: "fix" },
      {
        onAlternative: () => {},
        onError: (err) => errors.push(err),
      },
    );

    expect(errors).toHaveLength(1);
    expect(errors[0].message).toBe("HTTP 404");
  });

  it("sends correct request body with all fields", async () => {
    let receivedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/ch-2/rewrite", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return new HttpResponse(sseStream(["data: [DONE]"]), {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    await streamRewrite(
      "ch-2",
      "novel-1",
      {
        selection_text: "Hello world",
        context_before: "Before text",
        context_after: "After text",
        mode: "custom",
        custom_instructions: "Make it poetic",
        count: 3,
        language: "en",
      },
      { onAlternative: () => {}, onAlternativeFinal: () => {} },
    );

    expect(receivedBody).not.toBeNull();
    expect(receivedBody!.selection_text).toBe("Hello world");
    expect(receivedBody!.context_before).toBe("Before text");
    expect(receivedBody!.context_after).toBe("After text");
    expect(receivedBody!.mode).toBe("custom");
    expect(receivedBody!.custom_instructions).toBe("Make it poetic");
    expect(receivedBody!.count).toBe(3);
    expect(receivedBody!.language).toBe("en");
  });

  it("handles fallback when no alternative tags in response", async () => {
    const alternatives: { label: string; text: string }[] = [];

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-fb/rewrite",
        async () =>
          new HttpResponse(
            sseStream(['data: {"text":"Just plain rewritten text without tags."}', "data: [DONE]"]),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamRewrite(
      "ch-fb",
      "novel-1",
      { selection_text: "Original", mode: "tone" },
      {
        onAlternative: (label, text) => alternatives.push({ label, text }),
        onAlternativeFinal: () => {},
        onError: () => {},
      },
    );

    // Fallback: entire response = single alternative
    expect(alternatives).toHaveLength(1);
    expect(alternatives[0].label).toBe("Rewritten text");
  });

  it("skips malformed JSON lines", async () => {
    const alternatives: { label: string; text: string }[] = [];
    const onError = vi.fn();

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-mal/rewrite",
        async () =>
          new HttpResponse(
            sseStream([
              'data: {"text":"<alternative label=\\"Good\\">Text</alternative>"}',
              "data: {broken",
              "data: [DONE]",
            ]),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamRewrite(
      "ch-mal",
      "novel-1",
      { selection_text: "Original", mode: "fix" },
      {
        onAlternative: (label, text) => alternatives.push({ label, text }),
        onAlternativeFinal: () => {},
        onError,
      },
    );

    expect(alternatives).toHaveLength(1);
    expect(alternatives[0]).toEqual({ label: "Good", text: "Text" });
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ kind: "parse" }));
  });

  it("preserves completed alternatives when the stream fails", async () => {
    const alternatives: { label: string; text: string }[] = [];
    const onError = vi.fn();

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-partial/rewrite",
        async () =>
          new HttpResponse(
            new ReadableStream({
              start(controller) {
                controller.enqueue(
                  new TextEncoder().encode(
                    'data: {"text":"<alternative label=\\"A\\">Text</alternative>"}\n',
                  ),
                );
                setTimeout(() => controller.error(new Error("connection lost")), 0);
              },
            }),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamRewrite(
      "ch-partial",
      "novel-1",
      { selection_text: "Original", mode: "fix" },
      {
        onAlternative: (label, text) => alternatives.push({ label, text }),
        onError,
      },
    );

    expect(alternatives).toEqual([{ label: "A", text: "Text" }]);
    // msw 3 surfaces a failing mocked stream as a network abort (message
    // "aborted", cause ECONNRESET) instead of the handler's error text.
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ kind: "network" }));
  });
});
