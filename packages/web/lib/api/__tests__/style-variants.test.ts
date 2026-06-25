/**
 * Tests for streamStyleVariantRegeneration (CR-AUFG-07-22).
 *
 * Pattern: matches streamRewrite() in rewrite.test.ts exactly — uses the
 * shared MSW server, inline sseStream helper, and the same SSE parsing
 * semantics (parseAlternatives + <alternative> tag accumulation).
 */
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { setAccessToken } from "@/lib/api/client";
import {
  type StyleVariantRegenerateRequest,
  streamStyleVariantRegeneration,
} from "@/lib/api/generation";
import { server } from "@/mocks/server";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a SSE ReadableStream from chunk data lines (mirrors rewrite.test.ts). */
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
// Tests: streamStyleVariantRegeneration
// ---------------------------------------------------------------------------

describe("streamStyleVariantRegeneration", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("POSTs to /style-variants/regenerate and streams the variant", async () => {
    const alternatives: { label: string; text: string }[] = [];
    let capturedBody: StyleVariantRegenerateRequest | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/style-variants/regenerate", async ({ request }) => {
        capturedBody = (await request.json()) as StyleVariantRegenerateRequest;
        return new HttpResponse(
          sseStream([
            'data: {"type":"request_info","request_id":"sv-1"}',
            'data: {"text":"<alternative label=\\"Sensory\\">The damp moss clung to her fingers, releasing its earthy perfume.</alternative>"}',
            "data: [DONE]",
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }),
    );

    await streamStyleVariantRegeneration(
      "ch-1",
      "novel-1",
      {
        source_text: "The forest was dark and full of ancient trees.",
        style_variant: "more_sensory",
      },
      {
        onAlternative: (label, text) => alternatives.push({ label, text }),
        onAlternativeFinal: () => {},
        onError: () => {},
      },
    );

    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.style_variant).toBe("more_sensory");
    expect(capturedBody!.source_text).toBe("The forest was dark and full of ancient trees.");
    expect(alternatives).toHaveLength(1);
    expect(alternatives[0].label).toBe("Sensory");
  });

  it("sends correct request body with all fields", async () => {
    let receivedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/ch-2/style-variants/regenerate", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return new HttpResponse(sseStream(["data: [DONE]"]), {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    // RULE-17 contract parity: only the fields the backend
    // StyleVariantRegenerateRequest accepts are sent (source_text,
    // context_before, context_after, style_variant, tone, language,
    // source_mode).
    await streamStyleVariantRegeneration(
      "ch-2",
      "novel-1",
      {
        source_text: "A sufficiently long source text for the variant regeneration request.",
        style_variant: "leaner",
        tone: "balanced",
        context_before: "Text before the selection",
        context_after: "Text after the selection",
        language: "de",
        source_mode: "co_author",
      },
      { onAlternative: () => {}, onAlternativeFinal: () => {} },
    );

    expect(receivedBody).not.toBeNull();
    expect(receivedBody!.source_text).toBe(
      "A sufficiently long source text for the variant regeneration request.",
    );
    expect(receivedBody!.style_variant).toBe("leaner");
    expect(receivedBody!.tone).toBe("balanced");
    expect(receivedBody!.context_before).toBe("Text before the selection");
    expect(receivedBody!.context_after).toBe("Text after the selection");
    expect(receivedBody!.language).toBe("de");
    expect(receivedBody!.source_mode).toBe("co_author");
    // No out-of-contract fields are sent (RULE-17 parity with backend schema).
    expect(receivedBody!.author_instruction).toBeUndefined();
    expect(receivedBody!.source_generation_id).toBeUndefined();
    expect(receivedBody!.count).toBeUndefined();
  });

  it("calls onError on HTTP failure", async () => {
    const errors: Error[] = [];

    server.use(
      http.post("*/api/v1/writing/chapters/ch-err/style-variants/regenerate", () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );

    await streamStyleVariantRegeneration(
      "ch-err",
      "novel-1",
      { source_text: "Some text here.", style_variant: "leaner" },
      {
        onAlternative: () => {},
        onAlternativeFinal: () => {},
        onError: (e) => errors.push(e),
      },
    );

    expect(errors).toHaveLength(1);
    expect(errors[0].message).toBe("HTTP 404");
  });

  it("handles fallback when no alternative tags in response", async () => {
    const alternatives: { label: string; text: string }[] = [];

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-fb/style-variants/regenerate",
        async () =>
          new HttpResponse(
            sseStream([
              'data: {"text":"Plain variant text without any tags at all."}',
              "data: [DONE]",
            ]),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    await streamStyleVariantRegeneration(
      "ch-fb",
      "novel-1",
      { source_text: "Original text.", style_variant: "more_lyrical" },
      {
        onAlternative: (label, text) => alternatives.push({ label, text }),
        onAlternativeFinal: () => {},
        onError: () => {},
      },
    );

    expect(alternatives).toHaveLength(1);
    expect(alternatives[0].label).toBe("Rewritten text");
  });

  it("aborts cleanly on AbortSignal", async () => {
    const controller = new AbortController();

    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-abort/style-variants/regenerate",
        () =>
          new HttpResponse(sseStream(['data: {"text":"partial"}', "data: [DONE]"]), {
            headers: { "Content-Type": "text/event-stream" },
          }),
      ),
    );

    controller.abort();

    await expect(
      streamStyleVariantRegeneration(
        "ch-abort",
        "novel-1",
        { source_text: "Some text here.", style_variant: "leaner" },
        {
          onAlternative: () => {},
          onAlternativeFinal: () => {},
          onError: () => {},
        },
        controller.signal,
      ),
    ).resolves.toBeUndefined();
  });
});
