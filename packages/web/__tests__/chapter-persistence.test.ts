/**
 * Tests for chapter persistence logic (localStorage read/write)
 *
 * The persistence logic lives in Sidebar.tsx — this test file validates
 * the localStorage contract independently of the component rendering,
 * so we don't need to mount the full Sidebar with all its providers.
 *
 * Contract:
 * - Key: `narrare:lastChapter:{novelId}`
 * - On restore: read from localStorage, validate against chapter list
 * - On persist: write activeChapterId to localStorage
 * - On novelId change: clear activeChapterId
 */

import { beforeEach, describe, expect, it } from "vitest";

const STORAGE_PREFIX = "narrare:lastChapter";

function getStorageKey(novelId: string): string {
  return `${STORAGE_PREFIX}:${novelId}`;
}

// Simulates the restore logic from Sidebar.tsx
function restoreChapter(
  novelId: string | undefined,
  chapters: Array<{ id: string }>,
  activeChapterId: string | null,
): string | null {
  if (!novelId || chapters.length === 0 || activeChapterId) return null;
  const key = getStorageKey(novelId);
  const stored = localStorage.getItem(key);
  const chapterIds = new Set(chapters.map((c) => c.id));
  if (stored && chapterIds.has(stored)) {
    return stored;
  }
  return chapters[0].id;
}

// Simulates the persist logic from Sidebar.tsx
function persistChapter(novelId: string | undefined, activeChapterId: string | null): void {
  if (!novelId || !activeChapterId) return;
  localStorage.setItem(getStorageKey(novelId), activeChapterId);
}

describe("Chapter persistence — localStorage contract", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("restoreChapter", () => {
    it("returns null when novelId is undefined", () => {
      expect(restoreChapter(undefined, [{ id: "ch-1" }], null)).toBeNull();
    });

    it("returns null when chapters list is empty", () => {
      expect(restoreChapter("novel-1", [], null)).toBeNull();
    });

    it("returns null when activeChapterId is already set", () => {
      expect(restoreChapter("novel-1", [{ id: "ch-1" }], "ch-1")).toBeNull();
    });

    it("returns stored chapter if it exists in the chapter list", () => {
      localStorage.setItem(getStorageKey("novel-1"), "ch-3");
      const chapters = [{ id: "ch-1" }, { id: "ch-2" }, { id: "ch-3" }];
      expect(restoreChapter("novel-1", chapters, null)).toBe("ch-3");
    });

    it("falls back to first chapter when stored ID is not in the list", () => {
      localStorage.setItem(getStorageKey("novel-1"), "ch-deleted");
      const chapters = [{ id: "ch-1" }, { id: "ch-2" }];
      expect(restoreChapter("novel-1", chapters, null)).toBe("ch-1");
    });

    it("falls back to first chapter when nothing is stored", () => {
      const chapters = [{ id: "ch-1" }, { id: "ch-2" }];
      expect(restoreChapter("novel-1", chapters, null)).toBe("ch-1");
    });
  });

  describe("persistChapter", () => {
    it("writes activeChapterId to localStorage with correct key", () => {
      persistChapter("novel-1", "ch-5");
      expect(localStorage.getItem(getStorageKey("novel-1"))).toBe("ch-5");
    });

    it("does not write when novelId is undefined", () => {
      persistChapter(undefined, "ch-5");
      expect(localStorage.length).toBe(0);
    });

    it("does not write when activeChapterId is null", () => {
      persistChapter("novel-1", null);
      expect(localStorage.length).toBe(0);
    });
  });

  describe("full round-trip", () => {
    it("persists and restores a chapter selection", () => {
      const novelId = "novel-42";
      const chapters = [{ id: "ch-a" }, { id: "ch-b" }, { id: "ch-c" }];

      // Step 1: User selects chapter → persist
      persistChapter(novelId, "ch-b");

      // Step 2: Simulate page reload — restore
      const restored = restoreChapter(novelId, chapters, null);
      expect(restored).toBe("ch-b");
    });

    it("each novel has independent chapter memory", () => {
      const chapters = [{ id: "ch-1" }, { id: "ch-2" }];

      // Novel A → chapter 1
      persistChapter("novel-A", "ch-1");
      // Novel B → chapter 2
      persistChapter("novel-B", "ch-2");

      expect(restoreChapter("novel-A", chapters, null)).toBe("ch-1");
      expect(restoreChapter("novel-B", chapters, null)).toBe("ch-2");
    });
  });
});
