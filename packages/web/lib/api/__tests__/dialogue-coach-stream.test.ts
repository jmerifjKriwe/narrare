import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { streamDialogueCoach } from "@/lib/api/dialogue-coach-stream";
import { server } from "@/mocks/server";

/** Build a minimal SSE response body from typed event lines. */
function sse(events: object[]): string {
  return `${events.map((e) => `data: ${JSON.stringify(e)}`).join("\n\n")}\n\ndata: [DONE]\n\n`;
}

describe("streamDialogueCoach SSE client", () => {
  it("fires onProgress then onResult then onComplete", async () => {
    const result = {
      chapter_id: "ch-1",
      mode: "analyze",
      issues: [],
      adaptive_summary: "shaped by 2 voices",
    };
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(
          sse([
            { event: "progress", progress: "Analysing dialogue…" },
            { event: "result", result },
            { event: "done", is_final: true },
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );

    const onProgress = vi.fn();
    const onResult = vi.fn<(r: unknown) => void>();
    const onComplete = vi.fn();
    const onError = vi.fn();

    await streamDialogueCoach(
      "ch-1",
      { selection_text: '"Hello."', mode: "analyze" },
      { onProgress, onResult, onComplete, onError },
    );

    expect(onProgress).toHaveBeenCalledWith("Analysing dialogue…");
    expect(onResult).toHaveBeenCalledTimes(1);
    expect(onResult.mock.calls[0][0]).toMatchObject({ chapter_id: "ch-1" });
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
  });

  it("surfaces a terminal error event via onError", async () => {
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(sse([{ event: "error", error: "model unavailable", is_final: true }]), {
          headers: { "Content-Type": "text/event-stream" },
        }),
      ),
    );
    const onError = vi.fn();
    const onComplete = vi.fn();
    await streamDialogueCoach(
      "ch-1",
      { selection_text: "x", mode: "improve" },
      { onResult: vi.fn(), onError, onComplete },
    );
    expect(onError).toHaveBeenCalled();
    expect(onComplete).not.toHaveBeenCalled();
  });
});
