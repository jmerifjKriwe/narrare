/**
 * useRewriteActions tests — rewrite suggestion resolution.
 *
 * Verifies the extracted hook's contract in isolation: accept / insert-as-new /
 * reject / cancel translate a suggestion into the right editor mutation and
 * drive the shared rewrite setters + lifecycle ops. The editor mutation
 * helpers (replaceSelectionWithAIContent / insertAIContentAt) are mocked so the
 * hook's wiring can be asserted without a real ProseMirror instance.
 *
 * Covers:
 *  - acceptSuggestion replaces the selection at the suggestion position, then resets
 *  - insertAsNew inserts after the selection end, then resets
 *  - rejectSuggestion opens the rejection input when the reason is empty
 *  - rejectSuggestion resets when a reason is provided
 *  - handleRewriteCancel cancels both lifecycle ops and clears selection/phase
 *  - accept/insert are no-ops without an editor or suggestion
 */

import { renderHook } from "@testing-library/react";
import type { Editor } from "@tiptap/react";
import type { Dispatch, SetStateAction } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import type { AISuggestion, RewritePhase, RewriteSelection } from "../TipTapEditorController";

const replaceSelectionWithAIContent = vi.fn();
const insertAIContentAt = vi.fn();

vi.mock("../extensions/AIAnnotation", () => ({
  replaceSelectionWithAIContent: (...args: unknown[]) => replaceSelectionWithAIContent(...args),
  insertAIContentAt: (...args: unknown[]) => insertAIContentAt(...args),
}));

import { useRewriteActions } from "../useRewriteActions";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const editor = {} as Editor;

const suggestion: AISuggestion = {
  original: "orig",
  suggestions: ["alt-one", "alt-two"],
  labels: ["L1", "L2"],
  position: { from: 10, to: 20 },
};

function makeSetters() {
  return {
    setAiSuggestion: vi.fn() as unknown as Dispatch<SetStateAction<AISuggestion | null>>,
    setRewritePhase: vi.fn() as unknown as Dispatch<SetStateAction<RewritePhase>>,
    setRewriteSelection: vi.fn() as unknown as Dispatch<SetStateAction<RewriteSelection | null>>,
    setShowRejectionInput: vi.fn() as unknown as Dispatch<SetStateAction<boolean>>,
    setRejectionReason: vi.fn() as unknown as Dispatch<SetStateAction<string>>,
    setRewriteError: vi.fn() as unknown as Dispatch<SetStateAction<AIErrorResponse | null>>,
  };
}

function makeOps() {
  return { handleVariantCancel: vi.fn(), reset: vi.fn(), cancel: vi.fn() };
}

function renderActions(overrides: Partial<Parameters<typeof useRewriteActions>[0]> = {}) {
  const setters = makeSetters();
  const ops = makeOps();
  const result = renderHook(() =>
    useRewriteActions({
      editor,
      aiSuggestion: suggestion,
      selectedSuggestion: 0,
      rejectionReason: "",
      ops,
      setters,
      ...overrides,
    }),
  );
  return { ...result, setters, ops };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useRewriteActions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("acceptSuggestion replaces the selection and resets rewrite state", () => {
    const { result, setters, ops } = renderActions();

    result.current.acceptSuggestion();

    expect(replaceSelectionWithAIContent).toHaveBeenCalledWith(
      editor,
      expect.stringMatching(/^rewrite-\d+$/),
      "rewrite",
      "alt-one",
      10,
      20,
    );
    expect(insertAIContentAt).not.toHaveBeenCalled();
    expect(ops.handleVariantCancel).toHaveBeenCalledTimes(1);
    expect(ops.reset).toHaveBeenCalledTimes(1);
    expect(setters.setAiSuggestion).toHaveBeenCalledWith(null);
    expect(setters.setRewritePhase).toHaveBeenCalledWith("idle");
    expect(setters.setShowRejectionInput).toHaveBeenCalledWith(false);
    expect(setters.setRejectionReason).toHaveBeenCalledWith("");
    expect(setters.setRewriteError).toHaveBeenCalledWith(null);
  });

  it("insertAsNew inserts after the selection end and resets", () => {
    const { result, setters, ops } = renderActions({ selectedSuggestion: 1 });

    result.current.insertAsNew();

    expect(insertAIContentAt).toHaveBeenCalledWith(
      editor,
      expect.stringMatching(/^rewrite-\d+$/),
      "rewrite",
      "alt-two",
      20,
    );
    expect(replaceSelectionWithAIContent).not.toHaveBeenCalled();
    expect(ops.reset).toHaveBeenCalledTimes(1);
    expect(setters.setRewritePhase).toHaveBeenCalledWith("idle");
  });

  it("rejectSuggestion opens the rejection input when the reason is empty", () => {
    const { result, setters, ops } = renderActions({ rejectionReason: "   " });

    result.current.rejectSuggestion();

    expect(setters.setShowRejectionInput).toHaveBeenCalledWith(true);
    expect(ops.reset).not.toHaveBeenCalled();
    expect(setters.setAiSuggestion).not.toHaveBeenCalled();
  });

  it("rejectSuggestion resets state when a reason is provided", () => {
    const { result, setters, ops } = renderActions({ rejectionReason: "too formal" });

    result.current.rejectSuggestion();

    expect(ops.reset).toHaveBeenCalledTimes(1);
    expect(setters.setRewritePhase).toHaveBeenCalledWith("idle");
    expect(setters.setShowRejectionInput).toHaveBeenCalledWith(false);
  });

  it("handleRewriteCancel cancels both lifecycle ops and clears selection/phase", () => {
    const { result, setters, ops } = renderActions();

    result.current.handleRewriteCancel();

    expect(ops.handleVariantCancel).toHaveBeenCalledTimes(1);
    expect(ops.cancel).toHaveBeenCalledTimes(1);
    expect(setters.setRewritePhase).toHaveBeenCalledWith("idle");
    expect(setters.setRewriteSelection).toHaveBeenCalledWith(null);
  });

  it("acceptSuggestion is a no-op without an editor", () => {
    const { result, ops } = renderActions({ editor: null });

    result.current.acceptSuggestion();

    expect(replaceSelectionWithAIContent).not.toHaveBeenCalled();
    expect(ops.reset).not.toHaveBeenCalled();
  });

  it("acceptSuggestion is a no-op without a suggestion", () => {
    const { result, ops } = renderActions({ aiSuggestion: null });

    result.current.acceptSuggestion();

    expect(replaceSelectionWithAIContent).not.toHaveBeenCalled();
    expect(ops.reset).not.toHaveBeenCalled();
  });
});
