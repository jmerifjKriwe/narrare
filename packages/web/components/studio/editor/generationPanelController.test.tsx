/**
 * useGenerationPanelController tests — generation-panel orchestration hook.
 *
 * Verifies the controller composes its sub-hooks into the panel's API:
 * config defaults, handleGenerate → startGeneration + stream, handleStop →
 * stopGeneration, handleRegenerate → reject + restart, and the accept/reject
 * mutation wiring. The API + memory layers are mocked (mirroring
 * GenerationPanel.test.tsx) so the controller's composition logic is the SUT.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useGenerationPanelController } from "./generationPanelController";

// ---------------------------------------------------------------------------
// Mocks — API + memory layer (same surface as GenerationPanel.test.tsx).
// ---------------------------------------------------------------------------

const mockStartGeneration = vi.fn();
const mockStopGeneration = vi.fn();
const mockAcceptDraft = vi.fn();
const mockRejectDraft = vi.fn();
const mockStreamGeneration = vi.fn();

vi.mock("@/lib/api/generation", () => ({
  writingApi: {
    startGeneration: (...args: unknown[]) => mockStartGeneration(...args),
    stopGeneration: (...args: unknown[]) => mockStopGeneration(...args),
    acceptDraft: (...args: unknown[]) => mockAcceptDraft(...args),
    rejectDraft: (...args: unknown[]) => mockRejectDraft(...args),
  },
  streamGeneration: (...args: unknown[]) => mockStreamGeneration(...args),
}));

vi.mock("@/lib/hooks/useMemory", () => ({
  useMemoryStatus: () => ({
    eventCount: 5,
    confidence: 0.8,
    hasProfile: true,
    data: null,
  }),
  useRecordFeedback: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

// ---------------------------------------------------------------------------
// Wrapper + helpers
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

function renderController(overrides: { novelId?: string; chapterId?: string } = {}) {
  const onDraftAccepted = vi.fn();
  const t = vi.fn((key: string) => key) as unknown as (key: string) => string;
  const wrapper = makeWrapper();
  const result = renderHook(
    () =>
      useGenerationPanelController({
        novelId: overrides.novelId ?? "novel-1",
        chapterId: overrides.chapterId ?? "chapter-1",
        onDraftAccepted,
        t,
      }),
    { wrapper },
  );
  return { ...result, onDraftAccepted };
}

// streamGeneration calls onChunk then onComplete by default.
function streamEmits(text: string) {
  mockStreamGeneration.mockImplementation(
    async (_rid: string, onChunk: (c: { text: string }) => void, onComplete?: () => void) => {
      onChunk({ text });
      await onComplete?.();
    },
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useGenerationPanelController", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStartGeneration.mockResolvedValue({
      request_id: "gen-1",
      status: "pending",
      mode: "full_draft",
    });
    mockStopGeneration.mockResolvedValue({ request_id: "gen-1", status: "stopped", word_count: 0 });
    mockAcceptDraft.mockResolvedValue({
      request_id: "gen-1",
      chapter_id: "chapter-1",
      word_count: 10,
    });
    mockRejectDraft.mockResolvedValue({ request_id: "gen-1", status: "rejected" });
    mockStreamGeneration.mockResolvedValue(undefined);
  });

  it("initializes with default config state", () => {
    const { result } = renderController();

    expect(result.current.mode).toBe("full_draft");
    expect(result.current.outline).toBe("");
    expect(result.current.prompt).toBe("");
    expect(result.current.tone).toBe("balanced");
    expect(result.current.wordTarget).toBe(0);
    // targetNum defaults to 3000 when wordTarget is 0.
    expect(result.current.targetNum).toBe(3000);
    expect(result.current.phase).toBe("config");
    expect(result.current.draftText).toBe("");
    expect(result.current.eventCount).toBe(5);
  });

  it("exposes config setters that update the derived state", () => {
    const { result } = renderController();

    act(() => result.current.setWordTarget(1500));
    expect(result.current.wordTarget).toBe(1500);
    // targetNum mirrors wordTarget when > 0.
    expect(result.current.targetNum).toBe(1500);

    act(() => result.current.setMode("scene_by_scene"));
    expect(result.current.mode).toBe("scene_by_scene");

    act(() => result.current.setTone("dramatic"));
    expect(result.current.tone).toBe("dramatic");
  });

  it("handleGenerate starts a generation and streams chunks into draftText", async () => {
    streamEmits("Once upon a time");
    const { result } = renderController();

    act(() => result.current.handleGenerate());

    await waitFor(() => expect(result.current.draftText).toBe("Once upon a time"));

    expect(mockStartGeneration).toHaveBeenCalledWith(
      "chapter-1",
      "novel-1",
      expect.objectContaining({
        mode: "full_draft",
        tone: "balanced",
      }),
    );
    expect(mockStreamGeneration).toHaveBeenCalled();
  });

  it("transitions to the review phase once the stream completes", async () => {
    streamEmits("hello world");
    const { result } = renderController();

    act(() => result.current.handleGenerate());

    await waitFor(() => expect(result.current.phase).toBe("review"));
    expect(result.current.wordCount).toBe(2);
  });

  it("handleStop calls stopGeneration on the server", async () => {
    streamEmits("partial output here");
    const { result } = renderController();
    act(() => result.current.handleGenerate());
    await waitFor(() => expect(result.current.draftText).toBe("partial output here"));

    await act(async () => {
      await result.current.handleStop();
    });

    expect(mockStopGeneration).toHaveBeenCalledWith("gen-1");
  });

  it("handleRegenerate rejects the current draft and restarts the stream", async () => {
    streamEmits("first draft");
    const { result } = renderController();
    act(() => result.current.handleGenerate());
    await waitFor(() => expect(result.current.draftText).toBe("first draft"));

    // Second generation returns a different id + new text.
    mockStartGeneration.mockResolvedValue({
      request_id: "gen-2",
      status: "pending",
      mode: "full_draft",
    });
    streamEmits("second draft");

    await act(async () => {
      await result.current.handleRegenerate();
    });

    expect(mockRejectDraft).toHaveBeenCalledWith("gen-1");
    await waitFor(() => expect(result.current.draftText).toBe("second draft"));
  });

  it("acceptDraft mutates accept and invokes onDraftAccepted", async () => {
    streamEmits("final text");
    const { result, onDraftAccepted } = renderController();
    act(() => result.current.handleGenerate());
    await waitFor(() => expect(result.current.phase).toBe("review"));

    act(() => result.current.acceptDraft());
    await waitFor(() => expect(result.current.acceptMutation.isSuccess).toBe(true));

    expect(mockAcceptDraft).toHaveBeenCalledWith("gen-1");
    expect(onDraftAccepted).toHaveBeenCalledWith("final text");
  });

  it("rejectDraft mutates reject", async () => {
    streamEmits("draft");
    const { result } = renderController();
    act(() => result.current.handleGenerate());
    await waitFor(() => expect(result.current.phase).toBe("review"));

    act(() => result.current.rejectDraft());
    await waitFor(() => expect(result.current.rejectMutation.isSuccess).toBe(true));

    expect(mockRejectDraft).toHaveBeenCalledWith("gen-1");
  });

  it("buildRequest includes outline only for outline-capable modes (edge case)", async () => {
    const { result } = renderController();

    // interview_assisted: no outline, includes prompt + auto_continue.
    act(() => {
      result.current.setMode("interview_assisted");
      result.current.setPrompt("write a mystery");
    });

    act(() => result.current.handleGenerate());
    await waitFor(() => expect(mockStartGeneration).toHaveBeenCalled());

    const req = mockStartGeneration.mock.calls[0][2] as Record<string, unknown>;
    expect(req.mode).toBe("interview_assisted");
    expect(req.auto_continue).toBe(true);
    expect(req.prompt).toBe("write a mystery");
    expect(req.outline).toBeUndefined();
  });
});
