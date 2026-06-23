/**
 * useStyleVariantRegeneration tests (CR-AUFG-07-22).
 *
 * Verifies the extracted hook's contract in isolation. The SSE transport
 * (streamStyleVariantRegeneration) and error mapper are mocked so the hook's
 * state wiring can be driven deterministically without a network round-trip.
 *
 * Covers:
 *  - public return shape { styleVariant, handleStyleVariantRegenerate,
 *    handleVariantCancel }
 *  - handleStyleVariantRegenerate guard (no selection) + setter/stream driving
 *  - the stream's onAlternative / onError callbacks land in the setters
 *  - handleVariantCancel aborts the in-flight stream (RULE-20) and clears the
 *    selected variant
 *  - regenerating again aborts the previous in-flight stream
 */

import { act, renderHook } from "@testing-library/react";
import type { Dispatch, RefObject, SetStateAction } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import type { AISuggestion, RewritePhase, RewriteSelection } from "../TipTapEditorController";
import { useStyleVariantRegeneration } from "../useStyleVariantRegeneration";

// ---------------------------------------------------------------------------
// Hoisted state shared with the (hoisted) mock factories + tests.
// ---------------------------------------------------------------------------

type StreamCallbacks = {
  onAlternative: (label: string, text: string) => void;
  onAlternativeFinal?: (count: number) => void;
  onError?: (error: Error) => void;
};

const { capture, mappedError } = vi.hoisted(() => ({
  capture: {
    callbacks: undefined as StreamCallbacks | undefined,
    signal: undefined as AbortSignal | undefined,
  },
  mappedError: {
    kind: "http",
    status: 500,
    i18nKey: "aiActions.errorDefault",
    userMessage: "boom",
    retryable: false,
    cause: new Error("upstream"),
  } satisfies AIErrorResponse,
}));

vi.mock("@/lib/api/generation", () => ({
  streamStyleVariantRegeneration: vi.fn(
    async (
      _chapterId: unknown,
      _novelId: unknown,
      _request: unknown,
      callbacks: StreamCallbacks,
      signal?: AbortSignal,
    ) => {
      capture.callbacks = callbacks;
      capture.signal = signal;
    },
  ),
}));

vi.mock("@/lib/api/ai-error-mapping", () => ({
  // Always maps to a structured response so the onError branch fires.
  mapSSEError: vi.fn(() => mappedError),
}));

// ---------------------------------------------------------------------------
// Fixtures + harness
// ---------------------------------------------------------------------------

const selection: RewriteSelection = {
  text: "original text",
  from: 0,
  to: 13,
  contextBefore: "before",
  contextAfter: "after",
};

interface SetterBag {
  setAiSuggestion: Dispatch<SetStateAction<AISuggestion | null>>;
  setSelectedSuggestion: Dispatch<SetStateAction<number>>;
  setRewritePhase: Dispatch<SetStateAction<RewritePhase>>;
  setRewriteError: Dispatch<SetStateAction<AIErrorResponse | null>>;
}

function makeSetters(): SetterBag {
  return {
    setAiSuggestion: vi.fn() as unknown as Dispatch<SetStateAction<AISuggestion | null>>,
    setSelectedSuggestion: vi.fn() as unknown as Dispatch<SetStateAction<number>>,
    setRewritePhase: vi.fn() as unknown as Dispatch<SetStateAction<RewritePhase>>,
    setRewriteError: vi.fn() as unknown as Dispatch<SetStateAction<AIErrorResponse | null>>,
  };
}

function makeRef(value: RewriteSelection | null): RefObject<RewriteSelection | null> {
  return { current: value } as RefObject<RewriteSelection | null>;
}

function renderVariantHook(selectionOverride: RewriteSelection | null = selection) {
  const setters = makeSetters();
  const view = renderHook(() =>
    useStyleVariantRegeneration({
      context: {
        chapterId: "ch1",
        locale: "en",
        novelId: "nv1",
        rewriteSelectionRef: makeRef(selectionOverride),
      },
      setters,
    }),
  );
  return { setters, view };
}

beforeEach(() => {
  vi.clearAllMocks();
  capture.callbacks = undefined;
  capture.signal = undefined;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useStyleVariantRegeneration", () => {
  it("exposes the documented public contract", () => {
    const { view } = renderVariantHook();
    expect(view.result.current).toEqual(
      expect.objectContaining({
        handleStyleVariantRegenerate: expect.any(Function),
        handleVariantCancel: expect.any(Function),
        styleVariant: null,
      }),
    );
  });

  it("guards when there is no selection (no stream started)", () => {
    const { setters, view } = renderVariantHook(null);
    act(() => view.result.current.handleStyleVariantRegenerate("leaner"));

    expect(capture.callbacks).toBeUndefined();
    expect(setters.setRewritePhase).not.toHaveBeenCalled();
  });

  it("drives the setters and starts the stream on regenerate", () => {
    const { setters, view } = renderVariantHook();
    act(() => view.result.current.handleStyleVariantRegenerate("leaner"));

    expect(view.result.current.styleVariant).toBe("leaner");
    expect(setters.setRewritePhase).toHaveBeenCalledWith("streaming");
    expect(setters.setRewriteError).toHaveBeenCalledWith(null);
    expect(capture.callbacks).toBeDefined();
    expect(capture.signal).toBeInstanceOf(AbortSignal);
  });

  it("lands alternatives via the stream's onAlternative callback", () => {
    const { setters, view } = renderVariantHook();
    act(() => view.result.current.handleStyleVariantRegenerate("more_lyrical"));
    act(() => capture.callbacks?.onAlternative("Label A", "new text"));

    expect(setters.setAiSuggestion).toHaveBeenCalledTimes(1);
    expect(setters.setSelectedSuggestion).toHaveBeenCalledWith(0);
    expect(setters.setRewritePhase).toHaveBeenCalledWith("showing-alternatives");
  });

  it("maps stream errors to a structured response (onError branch)", () => {
    const { setters, view } = renderVariantHook();
    act(() => view.result.current.handleStyleVariantRegenerate("more_tense"));
    act(() => capture.callbacks?.onError?.(new Error("upstream")));

    expect(setters.setRewriteError).toHaveBeenCalledWith(mappedError);
    // onError transitions phase via a functional updater.
    expect(setters.setRewritePhase).toHaveBeenLastCalledWith(expect.any(Function));
  });

  it("handleVariantCancel aborts the in-flight stream and clears the variant (RULE-20)", () => {
    const { view } = renderVariantHook();
    act(() => view.result.current.handleStyleVariantRegenerate("leaner"));
    const signal = capture.signal;
    expect(signal?.aborted).toBe(false);

    act(() => view.result.current.handleVariantCancel());

    expect(signal?.aborted).toBe(true);
    expect(view.result.current.styleVariant).toBeNull();
  });

  it("aborts the previous stream when regenerating again (RULE-20 visible cancel)", () => {
    const { view } = renderVariantHook();
    act(() => view.result.current.handleStyleVariantRegenerate("leaner"));
    const firstSignal = capture.signal;

    act(() => view.result.current.handleStyleVariantRegenerate("more_lyrical"));

    expect(firstSignal?.aborted).toBe(true);
  });
});
