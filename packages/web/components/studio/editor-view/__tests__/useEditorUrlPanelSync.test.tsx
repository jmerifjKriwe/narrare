/**
 * useEditorUrlPanelSync tests — URL ↔ editor right-panel two-way sync.
 *
 * Regression (found by the ADR-084 acceptance E2E): the URL→store direction
 * must apply the ``panel`` param only when the URL itself changes. It used to
 * re-run on store-driven ``activeRightPanel`` changes with a STALE URL param
 * (the store→URL ``router.replace`` lands asynchronously) — opening the
 * session panel while ``?panel=generation`` was still in the URL re-opened
 * the generation panel one tick later and unmounted the freshly connected
 * SessionPanel (its WebSocket closed right after ``session_created``).
 */

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EditorRightPanelId } from "@/lib/stores/editorRightPanelState";
import { useEditorUrlPanelSync } from "../useEditorUrlPanelSync";

// ---------------------------------------------------------------------------
// Mocks — mutable module state so tests can simulate URL changes
// ---------------------------------------------------------------------------

const search = vi.hoisted(() => ({ value: "?panel=generation" }));
const mockReplace = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/novel/novel-1",
  useSearchParams: () => new URLSearchParams(search.value),
}));

// ---------------------------------------------------------------------------
// Harness
// ---------------------------------------------------------------------------

function renderSync(activePanel: EditorRightPanelId | null) {
  const openRightPanel = vi.fn();
  const utils = renderHook(
    ({ active }: { active: EditorRightPanelId | null }) =>
      useEditorUrlPanelSync({ activeRightPanel: active, openRightPanel }),
    { initialProps: { active: activePanel } },
  );
  return { openRightPanel, ...utils };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useEditorUrlPanelSync", () => {
  beforeEach(() => {
    search.value = "?panel=generation";
    mockReplace.mockClear();
  });

  it("applies the URL panel param on mount", () => {
    const { openRightPanel } = renderSync(null);
    expect(openRightPanel).toHaveBeenCalledWith("generation", "url");
  });

  it("does not clobber a store-driven panel switch with the stale URL param", () => {
    const { openRightPanel, rerender } = renderSync("generation");
    expect(openRightPanel).not.toHaveBeenCalled();

    // Store-driven switch (e.g. Start Session → "session"). The URL param
    // still says "generation" because router.replace has not landed yet —
    // re-opening "generation" here would unmount the new panel.
    act(() => rerender({ active: "session" }));
    expect(openRightPanel).not.toHaveBeenCalled();

    // router.replace lands and strips the (unsafe-to-deep-link) param.
    act(() => {
      search.value = "";
      rerender({ active: "session" });
    });
    expect(openRightPanel).not.toHaveBeenCalled();
  });

  it("re-applies when the URL panel param itself changes", () => {
    const { openRightPanel, rerender } = renderSync("generation");
    expect(openRightPanel).not.toHaveBeenCalled();

    act(() => {
      search.value = "?panel=metadata";
      rerender({ active: "generation" });
    });
    expect(openRightPanel).toHaveBeenCalledWith("metadata", "url");
  });

  it("ignores its own pending write landing after a store-driven panel switch", () => {
    // The exact ADR-084 E2E race: toolbar opens "generation" (write scheduled
    // while the URL has no param yet), "Start Session" flips the store to
    // "session", THEN the router.replace(?panel=generation) lands. Reading
    // that echo back must not reopen "generation".
    search.value = "";
    const { openRightPanel, rerender } = renderSync("generation");
    expect(mockReplace).toHaveBeenCalledTimes(1); // the pending write

    act(() => {
      search.value = "?panel=generation"; // our own write landing…
      rerender({ active: "session" }); // …while the store already moved on
    });
    expect(openRightPanel).not.toHaveBeenCalled();

    // A genuinely external param change still applies afterwards.
    act(() => {
      search.value = "?panel=metadata";
      rerender({ active: "session" });
    });
    expect(openRightPanel).toHaveBeenCalledWith("metadata", "url");
  });
});
