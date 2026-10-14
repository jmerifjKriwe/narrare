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

function renderController(
  overrides: {
    novelId?: string;
    chapterId?: string;
    scenePlans?: Array<Record<string, unknown>>;
  } = {},
) {
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
        scenePlans: overrides.scenePlans as never,
      }),
    { wrapper },
  );
  return { ...result, onDraftAccepted };
}

// streamGeneration calls onChunk then onComplete by default. The chunk
// carries is_final — per the stream contract (M06), a stream that ends
// without a final chunk is a dead stream, not a completed one.
function streamEmits(text: string) {
  mockStreamGeneration.mockImplementation(
    async (
      _rid: string,
      onChunk: (c: { text: string; is_final?: boolean }) => void,
      onComplete?: () => void,
    ) => {
      onChunk({ text, is_final: true });
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

    expect(mockAcceptDraft).toHaveBeenCalledWith("gen-1", "final text");
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

  it("threads injected scenePlans into scene_by_scene requests (spec §8.1)", async () => {
    const scene = {
      id: "scene-1",
      title: "The Gate",
      pov_character_ref: { id: null, name: "John" },
      location_ref: null,
      present_characters: [{ id: null, name: "Mara", goal: "Stop him" }],
      purpose: "Reach the gate",
      conflict: "",
      resolution: "",
      beats: [],
      status: "planned",
    };
    const { result } = renderController({ scenePlans: [scene] });

    act(() => result.current.setMode("scene_by_scene"));
    act(() => result.current.handleGenerate());
    await waitFor(() => expect(mockStartGeneration).toHaveBeenCalled());

    const req = mockStartGeneration.mock.calls[0][2] as Record<string, unknown>;
    // Identity-free GenerateScene shape (RULE-17 mirror), not the raw ScenePlan.
    expect(req.scenes).toEqual([
      {
        title: "The Gate",
        pov_character_name: "John",
        location_name: "",
        present_characters: [{ name: "Mara", goal: "Stop him" }],
        purpose: "Reach the gate",
        conflict: "",
        resolution: "",
        beats: [],
        status: "planned",
      },
    ]);
    // Default ON while plans exist — no explicit toggle needed.
    expect(result.current.useScenePlans).toBe(true);
  });

  it("omits scenes when the chapter has none, even in scene_by_scene mode", async () => {
    const { result } = renderController({ scenePlans: [] });

    act(() => result.current.setMode("scene_by_scene"));
    act(() => result.current.handleGenerate());
    await waitFor(() => expect(mockStartGeneration).toHaveBeenCalled());

    const req = mockStartGeneration.mock.calls[0][2] as Record<string, unknown>;
    expect(req.scenes).toBeUndefined();
  });

  it("treats a stream that completes without is_final as an error (M06)", async () => {
    mockStartGeneration.mockResolvedValue({ request_id: "gen-m06", status: "pending" });
    mockStreamGeneration.mockImplementation(
      async (_rid: string, onChunk: (c: { text: string; is_final?: boolean }) => void) => {
        onChunk({ text: "" }); // silent death: no is_final, stream just ends
      },
    );

    const { result } = renderHook(
      () =>
        useGenerationPanelController({
          novelId: "novel-1",
          chapterId: "chapter-1",
          onDraftAccepted: vi.fn(),
          t: (key: string) => key,
        }),
      { wrapper: makeWrapper() },
    );

    act(() => result.current.handleGenerate());

    await waitFor(() => expect(result.current.phase).toBe("error"));
    expect(result.current.error?.i18nKey).toBe("aiActions.errorDefault");
  });

  it("accepts with the streamed draft text as modified_text (M06 + Task 1 contract)", async () => {
    mockStartGeneration.mockResolvedValue({ request_id: "gen-m06b", status: "pending" });
    mockStreamGeneration.mockImplementation(
      async (_rid: string, onChunk: (c: { text: string; is_final?: boolean }) => void) => {
        onChunk({ text: "The harbour bell rang twice." });
        onChunk({ text: " Done.", is_final: true });
      },
    );
    mockAcceptDraft.mockResolvedValue({ request_id: "gen-m06b", chapter_id: "c1", word_count: 5 });

    const onDraftAccepted = vi.fn();
    const { result } = renderHook(
      () =>
        useGenerationPanelController({
          novelId: "novel-1",
          chapterId: "chapter-1",
          onDraftAccepted,
          t: (key: string) => key,
        }),
      { wrapper: makeWrapper() },
    );

    act(() => result.current.handleGenerate());
    await waitFor(() => expect(result.current.phase).toBe("review"));
    act(() => result.current.acceptDraft());

    await waitFor(() =>
      expect(mockAcceptDraft).toHaveBeenCalledWith(
        "gen-m06b",
        "The harbour bell rang twice. Done.",
      ),
    );
    await waitFor(() =>
      expect(onDraftAccepted).toHaveBeenCalledWith("The harbour bell rang twice. Done."),
    );
  });
});
