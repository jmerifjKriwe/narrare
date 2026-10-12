/**
 * useEditorCommandPalette tests — extend wiring (audit B08).
 *
 * `commandContext.startExtend` was a `() => {}` stub; the palette's
 * "Continue Writing" commands were no-ops. The hook now receives the real
 * handler from EditorView.
 *
 * @module useEditorCommandPalette.test
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useEditorCommandPalette } from "../useEditorCommandPalette";

function makeParams() {
  return {
    handleSave: vi.fn(async () => {}),
    handleStartGeneration: vi.fn(),
    handleStopGeneration: vi.fn(async () => {}),
    handleAcceptDraft: vi.fn(),
    handleRejectDraft: vi.fn(async () => {}),
    handleStartExtend: vi.fn(),
  };
}

describe("useEditorCommandPalette", () => {
  it("wires startExtend to the host handler (B08)", () => {
    const params = makeParams();
    const { result } = renderHook(() => useEditorCommandPalette(params));

    result.current.commandContext.startExtend("short");

    expect(params.handleStartExtend).toHaveBeenCalledTimes(1);
    expect(params.handleStartExtend).toHaveBeenCalledWith("short");
  });

  it("keeps the commandContext stable across re-renders with stable inputs", () => {
    const params = makeParams();
    const { result, rerender } = renderHook(() => useEditorCommandPalette(params));
    const first = result.current.commandContext;
    rerender();
    expect(result.current.commandContext).toBe(first);
  });
});
