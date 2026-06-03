import { describe, expect, it, vi } from "vitest";
import { connectSSE } from "../streaming";
import { extractExpressionsSSE, timelineApi } from "../timeline";

vi.mock("../streaming", () => ({
  connectSSE: vi.fn(),
}));

const mockConnectSSE = vi.mocked(connectSSE);

describe("timelineApi streaming extraction", () => {
  it("does not expose a REST wrapper for the SSE extraction endpoint", () => {
    expect("extractExpressions" in timelineApi).toBe(false);
  });

  it("streams timeline extraction through the shared connectSSE transport", async () => {
    const onEvent = vi.fn();
    const onComplete = vi.fn();
    const onError = vi.fn();
    const controller = new AbortController();

    mockConnectSSE.mockResolvedValue(undefined);

    await extractExpressionsSSE(
      "novel-1",
      ["chapter-1", "chapter-2"],
      { onEvent, onComplete, onError },
      controller.signal,
    );

    expect(mockConnectSSE).toHaveBeenCalledWith({
      url: "/planning/timeline/novel-1/extract",
      body: { chapter_ids: ["chapter-1", "chapter-2"] },
      onChunk: onEvent,
      onComplete: expect.any(Function),
      onError,
      signal: controller.signal,
    });
  });

  it("forwards stream completion to the caller", async () => {
    const onComplete = vi.fn();

    mockConnectSSE.mockImplementation(async ({ onComplete: complete }) => {
      complete?.(undefined);
    });

    await extractExpressionsSSE("novel-1", ["chapter-1"], {
      onEvent: vi.fn(),
      onComplete,
      onError: vi.fn(),
    });

    expect(onComplete).toHaveBeenCalledOnce();
  });
});
