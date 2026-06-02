/**
 * Content recovery tests — sessionStorage-based editor content persistence.
 *
 * Tests:
 * 1. saveContent stores data in sessionStorage
 * 2. recoverContent retrieves and clears data
 * 3. hasRecoverableContent checks existence
 * 4. recoverIfNewer restores only when newer than DB
 * 5. recoverIfNewer discards older saved content
 * 6. Pre-redirect callback registration and invocation
 * 7. saveBeforeRedirect is a no-op without registered callback
 * 8. Unregister removes the callback
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  hasRecoverableContent,
  recoverContent,
  recoverIfNewer,
  registerPreRedirectSave,
  type SavedContent,
  saveBeforeRedirect,
  saveContent,
} from "@/lib/hooks/use-content-recovery";

// ---------------------------------------------------------------------------
// Mock sessionStorage
// ---------------------------------------------------------------------------

const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
});

vi.stubGlobal("sessionStorage", {
  getItem: (key: string) => store.get(key) ?? null,
  setItem: (key: string, value: string) => store.set(key, value),
  removeItem: (key: string) => store.delete(key),
  clear: () => store.clear(),
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Content Recovery", () => {
  afterEach(() => {
    store.clear();
  });

  it("saveContent stores data in sessionStorage", () => {
    saveContent("chapter-1", "<p>Hello world</p>");

    const key = "narrare:unsavedContent:chapter-1";
    expect(store.has(key)).toBe(true);
    const parsed = JSON.parse(store.get(key)!) as SavedContent;
    expect(parsed.chapterId).toBe("chapter-1");
    expect(parsed.content).toBe("<p>Hello world</p>");
    expect(parsed.timestamp).toBeTypeOf("number");
  });

  it("recoverContent retrieves and clears data", () => {
    saveContent("chapter-2", "<p>Test content</p>");

    const recovered = recoverContent("chapter-2");
    expect(recovered).not.toBeNull();
    expect(recovered!.chapterId).toBe("chapter-2");
    expect(recovered!.content).toBe("<p>Test content</p>");

    // Should be cleared after recovery
    expect(recoverContent("chapter-2")).toBeNull();
  });

  it("recoverContent returns null for missing chapter", () => {
    expect(recoverContent("nonexistent")).toBeNull();
  });

  it("hasRecoverableContent returns true when data exists", () => {
    saveContent("chapter-3", "<p>Content</p>");
    expect(hasRecoverableContent("chapter-3")).toBe(true);
    expect(hasRecoverableContent("chapter-99")).toBe(false);
  });

  it("recoverIfNewer restores content when newer than DB", () => {
    const now = Date.now();
    const dbUpdatedAt = new Date(now - 10_000).toISOString(); // 10s ago

    // Save with a recent timestamp
    saveContent("chapter-4", "<p>Newer content</p>");

    const recovered = recoverIfNewer("chapter-4", dbUpdatedAt);
    expect(recovered).not.toBeNull();
    expect(recovered!.content).toBe("<p>Newer content</p>");
  });

  it("recoverIfNewer discards content older than DB", () => {
    const now = Date.now();
    const dbUpdatedAt = new Date(now + 10_000).toISOString(); // 10s in future

    saveContent("chapter-5", "<p>Older content</p>");

    const recovered = recoverIfNewer("chapter-5", dbUpdatedAt);
    expect(recovered).toBeNull();
  });
});

describe("Pre-redirect save callback", () => {
  afterEach(() => {
    // Reset any registered callback
    registerPreRedirectSave(() => {});
  });

  it("saveBeforeRedirect calls registered callback", () => {
    const mockSave = vi.fn();
    registerPreRedirectSave(mockSave);

    saveBeforeRedirect();
    expect(mockSave).toHaveBeenCalledOnce();
  });

  it("saveBeforeRedirect is a no-op without registered callback", () => {
    // Register and unregister
    const unregister = registerPreRedirectSave(() => {
      throw new Error("Should not be called");
    });
    unregister();

    // Should not throw
    expect(() => saveBeforeRedirect()).not.toThrow();
  });

  it("unregister removes the callback", () => {
    const mockSave = vi.fn();
    const unregister = registerPreRedirectSave(mockSave);
    unregister();

    saveBeforeRedirect();
    expect(mockSave).not.toHaveBeenCalled();
  });
});
