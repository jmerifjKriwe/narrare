/**
 * useCoAuthorStyleVariant hook tests (CR-AUFG-07-22 Increment B).
 *
 * Verifies the Co-Author variant lifecycle end-to-end against the real MSW
 * server (mirrors lib/api/__tests__/style-variants.test.ts), with particular
 * focus on the source_mode contract: the Co-Author surface MUST send
 * source_mode="co_author" and the Co-Author output as source_text.
 *
 * Tests:
 * 1. Selecting a variant POSTs with source_mode="co_author" + source_text=streamedText
 * 2. The regenerated alternative text flows into variantText
 * 3. HTTP failure maps to variantError and clears isVariantStreaming
 * 4. No request fires when streamedText is empty (guards against 422)
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useCoAuthorStyleVariant } from "@/components/studio/editor/_components/useCoAuthorStyleVariant";
import { setAccessToken } from "@/lib/api/client";
import { server } from "@/mocks/server";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build an SSE ReadableStream from chunk data lines (mirrors style-variants.test.ts). */
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

const STREAMED_OUTPUT =
  "The rain fell in silver sheets across the abandoned courtyard, pooling in the cracks of the old stone fountain.";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useCoAuthorStyleVariant", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  it("sends source_mode='co_author' and source_text=streamedText on variant select", async () => {
    let capturedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/style-variants/regenerate", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return new HttpResponse(
          sseStream([
            'data: {"text":"<alternative label=\\"Sensory\\">Silver rain pooled in the fountain cracks.</alternative>"}',
            "data: [DONE]",
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }),
    );

    const { result } = renderHook(() =>
      useCoAuthorStyleVariant({
        novelId: "novel-1",
        chapterId: "ch-1",
        locale: "en",
        streamedText: STREAMED_OUTPUT,
      }),
    );

    act(() => result.current.handleVariantSelect("more_sensory"));

    await waitFor(() => {
      expect(capturedBody).not.toBeNull();
    });

    await act(async () => {});

    // The core Increment-B contract: the Co-Author surface MUST select the
    // co_author source mode so the backend uses the CO_AUTHOR pipeline.
    expect(capturedBody!.source_mode).toBe("co_author");
    expect(capturedBody!.source_text).toBe(STREAMED_OUTPUT);
    expect(capturedBody!.style_variant).toBe("more_sensory");
    expect(capturedBody!.language).toBe("en");
  });

  it("flows the regenerated alternative into variantText and clears streaming", async () => {
    server.use(
      http.post(
        "*/api/v1/writing/chapters/ch-1/style-variants/regenerate",
        () =>
          new HttpResponse(
            sseStream([
              'data: {"text":"<alternative label=\\"Lyrical\\">The rain whispered down in long, soft ribbons of light.</alternative>"}',
              "data: [DONE]",
            ]),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );

    const { result } = renderHook(() =>
      useCoAuthorStyleVariant({
        novelId: "novel-1",
        chapterId: "ch-1",
        locale: "en",
        streamedText: STREAMED_OUTPUT,
      }),
    );

    expect(result.current.selectedVariant).toBeNull();
    expect(result.current.variantText).toBe("");

    act(() => result.current.handleVariantSelect("more_lyrical"));

    await waitFor(() => {
      // Variant is selected and the regenerated alternative flows in; streaming
      // clears once the closing tag is parsed.
      expect(result.current.selectedVariant).toBe("more_lyrical");
      expect(result.current.variantText).toContain("ribbons of light");
      expect(result.current.isVariantStreaming).toBe(false);
    });

    await act(async () => {});
  });

  it("maps an HTTP failure to variantError and clears isVariantStreaming", async () => {
    server.use(
      http.post("*/api/v1/writing/chapters/ch-err/style-variants/regenerate", () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );

    const { result } = renderHook(() =>
      useCoAuthorStyleVariant({
        novelId: "novel-1",
        chapterId: "ch-err",
        locale: "en",
        streamedText: STREAMED_OUTPUT,
      }),
    );

    act(() => result.current.handleVariantSelect("leaner"));

    await waitFor(() => {
      expect(result.current.variantError).not.toBeNull();
      expect(result.current.isVariantStreaming).toBe(false);
    });

    await act(async () => {});
  });

  it("does not fire a request when streamedText is empty", async () => {
    let requestCount = 0;

    server.use(
      http.post("*/api/v1/writing/chapters/ch-1/style-variants/regenerate", () => {
        requestCount++;
        return new HttpResponse(sseStream(["data: [DONE]"]), {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    const { result } = renderHook(() =>
      useCoAuthorStyleVariant({
        novelId: "novel-1",
        chapterId: "ch-1",
        locale: "en",
        streamedText: "",
      }),
    );

    act(() => result.current.handleVariantSelect("more_tense"));

    // Allow any pending microtasks to flush.
    await Promise.resolve();
    expect(requestCount).toBe(0);
    expect(result.current.selectedVariant).toBeNull();
  });
});
