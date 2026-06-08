/**
 * Unit tests for useSeenTooltips hook.
 *
 * Covers: isSeen() returns false for new tooltips, markSeen() persists to
 * localStorage, isSeen() returns true after markSeen(), resetAll() clears
 * all seen tooltips, persistence across re-renders.
 *
 * @module useSeenTooltips.test
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSeenTooltips } from "@/lib/hooks/useSeenTooltips";

// ---------------------------------------------------------------------------
// localStorage mock
// ---------------------------------------------------------------------------

const STORAGE_KEY = "narrare_seen_tooltips";

let store: Record<string, string> = {};

beforeEach(() => {
  store = {};
  // Use Object.defineProperty on localStorage directly to ensure the hook's
  // reads/writes go through our in-memory store.
  vi.spyOn(localStorage, "getItem").mockImplementation((key: string) => store[key] ?? null);
  vi.spyOn(localStorage, "setItem").mockImplementation((key: string, value: string) => {
    store[key] = value;
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  store = {};
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useSeenTooltips", () => {
  // -------------------------------------------------------------------------
  // isSeen() returns false for new tooltips
  // -------------------------------------------------------------------------

  it("returns false for unseen tooltips", () => {
    const { result } = renderHook(() => useSeenTooltips());
    expect(result.current.isSeen("feature-tour")).toBe(false);
    expect(result.current.isSeen("co-author-tip")).toBe(false);
  });

  // -------------------------------------------------------------------------
  // markSeen() stores in localStorage
  // -------------------------------------------------------------------------

  it("markSeen() persists to localStorage", () => {
    const { result } = renderHook(() => useSeenTooltips());

    act(() => {
      result.current.markSeen("feature-tour");
    });

    // Verify localStorage was written
    const stored = JSON.parse(store[STORAGE_KEY]) as string[];
    expect(stored).toContain("feature-tour");
  });

  // -------------------------------------------------------------------------
  // isSeen() returns true after markSeen()
  // -------------------------------------------------------------------------

  it("returns true after markSeen()", () => {
    const { result } = renderHook(() => useSeenTooltips());

    act(() => {
      result.current.markSeen("feature-tour");
    });

    expect(result.current.isSeen("feature-tour")).toBe(true);

    // Other tooltips still unseen
    expect(result.current.isSeen("co-author-tip")).toBe(false);
  });

  // -------------------------------------------------------------------------
  // resetAll() clears all seen tooltips
  // -------------------------------------------------------------------------

  it("resetAll() clears all seen tooltips", () => {
    const { result } = renderHook(() => useSeenTooltips());

    act(() => {
      result.current.markSeen("feature-tour");
      result.current.markSeen("co-author-tip");
    });

    expect(result.current.isSeen("feature-tour")).toBe(true);
    expect(result.current.isSeen("co-author-tip")).toBe(true);

    act(() => {
      result.current.resetAll();
    });

    expect(result.current.isSeen("feature-tour")).toBe(false);
    expect(result.current.isSeen("co-author-tip")).toBe(false);
  });

  // -------------------------------------------------------------------------
  // Persistence across re-renders
  // -------------------------------------------------------------------------

  it("persists seen state across re-renders", () => {
    const { result, rerender } = renderHook(() => useSeenTooltips());

    act(() => {
      result.current.markSeen("feature-tour");
    });

    // Re-render the hook (simulates component re-mount)
    rerender();

    expect(result.current.isSeen("feature-tour")).toBe(true);
  });

  // -------------------------------------------------------------------------
  // markSeen() is idempotent
  // -------------------------------------------------------------------------

  it("markSeen() is idempotent — calling twice does not duplicate entries", () => {
    const { result } = renderHook(() => useSeenTooltips());

    act(() => {
      result.current.markSeen("feature-tour");
      result.current.markSeen("feature-tour");
    });

    const stored = JSON.parse(store[STORAGE_KEY]) as string[];
    const count = stored.filter((v) => v === "feature-tour").length;
    expect(count).toBe(1);
  });

  // -------------------------------------------------------------------------
  // Handles corrupted localStorage data gracefully
  // -------------------------------------------------------------------------

  it("handles corrupted localStorage data gracefully", () => {
    store[STORAGE_KEY] = "not-valid-json{";

    const { result } = renderHook(() => useSeenTooltips());

    // Should not throw, just treat as empty
    expect(result.current.isSeen("feature-tour")).toBe(false);
  });

  it("handles non-array localStorage data gracefully", () => {
    store[STORAGE_KEY] = JSON.stringify("just-a-string");

    const { result } = renderHook(() => useSeenTooltips());

    expect(result.current.isSeen("feature-tour")).toBe(false);
  });
});
