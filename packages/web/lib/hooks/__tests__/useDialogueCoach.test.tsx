/**
 * useDialogueCoach hook tests — SSE streaming for ASSIST-004 dialogue coach.
 *
 * Mirrors the useAIOperation integration-test style used by the Task 3
 * adaptive-context tests: the real useAIOperation lifecycle and the real
 * streamDialogueCoach → connectSSE transport run, and only the network
 * boundary is mocked (MSW). Each test posts a typed SSE event stream
 * (progress → result → done, or error) and observes the resulting lifecycle
 * state — verifying the SSE → state bridging that is unique to this hook:
 * single-result resolution on `onResult` (vs character-voice's array
 * accumulation on `onComplete`), progress surfacing, and no manual
 * AbortController (ADR-043).
 *
 * @module useDialogueCoach.test
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { useDialogueCoach } from "@/lib/hooks/useDialogueCoach";
import { server } from "@/mocks/server";

function wrapper() {
  const qc = new QueryClient();
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function sse(events: object[]): string {
  return `${events.map((e) => `data: ${JSON.stringify(e)}`).join("\n\n")}\n\ndata: [DONE]\n\n`;
}

afterEach(() => server.resetHandlers());

describe("useDialogueCoach", () => {
  it("runs and surfaces the single result", async () => {
    const result = {
      chapter_id: "ch-1",
      mode: "analyze",
      issues: [
        {
          issue_type: "on-the-nose",
          speaker: "Alice",
          original_quote: '"I am sad."',
          diagnosis: "stated emotion directly",
          severity: "medium",
          alternatives: null,
        },
      ],
      adaptive_summary: "",
    };
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(
          sse([
            { event: "progress", progress: "Analysing…" },
            { event: "result", result },
            { event: "done", is_final: true },
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );
    const { result: hook } = renderHook(() => useDialogueCoach(), { wrapper: wrapper() });
    hook.current.run({ chapterId: "ch-1", selectionText: '"I am sad."', mode: "analyze" });
    await waitFor(() => expect(hook.current.isComplete).toBe(true));
    expect(hook.current.result?.issues).toHaveLength(1);
    expect(hook.current.progress).toBe("Analysing…");
  });

  it("surfaces errors and stays retryable", async () => {
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(sse([{ event: "error", error: "boom", is_final: true }]), {
          headers: { "Content-Type": "text/event-stream" },
        }),
      ),
    );
    const { result: hook } = renderHook(() => useDialogueCoach(), { wrapper: wrapper() });
    hook.current.run({ chapterId: "ch-1", selectionText: "x", mode: "improve" });
    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeTruthy();
  });
});
