/**
 * useUnblockStream tests — request-body contract for Writer's Unblock.
 *
 * Audit B02 regression: the hook omitted `novel_id` from the POST body even
 * though `StorySuggestRequest` requires it (422 "Field required" rendered as
 * "Connection lost").
 *
 * @module useUnblockStream.test
 */

import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Rest-parameter signature so mock.calls entries are `unknown[]` (the stream
// stays pending forever, mirroring an open SSE stream until the test asserts).
const streamStorySuggestions = vi.hoisted(() =>
  vi.fn(async (..._args: unknown[]) => new Promise<void>(() => {})),
);

vi.mock("@/lib/api/story-suggest-stream", () => ({
  streamStorySuggestions: (...args: unknown[]) => streamStorySuggestions(...args),
}));

import { useUnblockStream } from "@/components/studio/editor/useUnblockStream";

describe("useUnblockStream", () => {
  beforeEach(() => {
    streamStorySuggestions.mockClear();
  });

  it("sends novel_id in the request body (B02)", async () => {
    const { result } = renderHook(() => useUnblockStream("novel-1", "chapter-9"));

    result.current.request("Stuck at the door scene");

    await waitFor(() => expect(streamStorySuggestions).toHaveBeenCalled());
    const body = streamStorySuggestions.mock.calls[0][1] as Record<string, unknown>;
    expect(body.novel_id).toBe("novel-1");
    expect(body.chapter_id).toBe("chapter-9");
    expect(body.author_instructions).toBe("Stuck at the door scene");
  });
});
