/**
 * KB Interview Resume tests — localStorage-based interview persistence.
 *
 * Tests:
 * 1. savePendingInterview stores data in localStorage
 * 2. getPendingInterview retrieves data without clearing
 * 3. clearPendingInterview removes stored data
 * 4. hasPendingInterview checks existence
 * 5. Multiple saves overwrite previous data
 * 6. Corrupted data returns null gracefully
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearPendingInterview,
  getPendingInterview,
  hasPendingInterview,
  isInterviewResumePersistenceDisabled,
  type PendingInterview,
  savePendingInterview,
  setInterviewResumePersistenceDisabled,
} from "@/lib/hooks/use-kb-interview-resume";

// ---------------------------------------------------------------------------
// Mock localStorage
// ---------------------------------------------------------------------------

const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
});

vi.stubGlobal("localStorage", {
  getItem: (key: string) => store.get(key) ?? null,
  setItem: (key: string, value: string) => store.set(key, value),
  removeItem: (key: string) => store.delete(key),
  clear: () => store.clear(),
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KB Interview Resume", () => {
  afterEach(() => {
    store.clear();
  });

  it("savePendingInterview stores data in localStorage", () => {
    savePendingInterview("novel-1", "session-abc", "character");

    const key = "narrare:kbInterview:novel-1";
    expect(store.has(key)).toBe(true);
    const parsed = JSON.parse(store.get(key)!) as PendingInterview;
    expect(parsed.sessionId).toBe("session-abc");
    expect(parsed.entityType).toBe("character");
    expect(parsed.savedAt).toBeTypeOf("number");
    expect(parsed.expiresAt).toBeGreaterThan(parsed.savedAt);
  });

  it("getPendingInterview retrieves data without clearing", () => {
    savePendingInterview("novel-1", "session-abc", "location");

    const result = getPendingInterview("novel-1");
    expect(result).not.toBeNull();
    expect(result!.sessionId).toBe("session-abc");
    expect(result!.entityType).toBe("location");

    // Data should still be there
    const result2 = getPendingInterview("novel-1");
    expect(result2).not.toBeNull();
  });

  it("getPendingInterview returns null for missing project", () => {
    expect(getPendingInterview("nonexistent")).toBeNull();
  });

  it("clearPendingInterview removes stored data", () => {
    savePendingInterview("novel-1", "session-abc", "character");
    expect(hasPendingInterview("novel-1")).toBe(true);

    clearPendingInterview("novel-1");
    expect(hasPendingInterview("novel-1")).toBe(false);
  });

  it("hasPendingInterview checks existence", () => {
    expect(hasPendingInterview("novel-1")).toBe(false);
    savePendingInterview("novel-1", "session-abc", "character");
    expect(hasPendingInterview("novel-1")).toBe(true);
  });

  it("multiple saves overwrite previous data", () => {
    savePendingInterview("novel-1", "session-1", "character");
    savePendingInterview("novel-1", "session-2", "location");

    const result = getPendingInterview("novel-1");
    expect(result!.sessionId).toBe("session-2");
    expect(result!.entityType).toBe("location");
  });

  it("corrupted data returns null gracefully", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    store.set("narrare:kbInterview:novel-1", "not valid json");

    const result = getPendingInterview("novel-1");
    expect(result).toBeNull();
    expect(store.has("narrare:kbInterview:novel-1")).toBe(false);
    warnSpy.mockRestore();
  });

  it("expires and clears pending interviews after TTL", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-03T10:00:00Z"));
    savePendingInterview("novel-1", "session-ttl", "character", 1000);

    expect(hasPendingInterview("novel-1")).toBe(true);

    vi.setSystemTime(new Date("2026-06-03T10:00:02Z"));
    expect(getPendingInterview("novel-1")).toBeNull();
    expect(store.has("narrare:kbInterview:novel-1")).toBe(false);
    vi.useRealTimers();
  });

  it("does not persist interviews when persistence is disabled", () => {
    setInterviewResumePersistenceDisabled(true);

    savePendingInterview("novel-1", "session-private", "character");

    expect(isInterviewResumePersistenceDisabled()).toBe(true);
    expect(hasPendingInterview("novel-1")).toBe(false);
    expect(store.has("narrare:kbInterview:novel-1")).toBe(false);
  });

  it("allows persistence to be re-enabled", () => {
    setInterviewResumePersistenceDisabled(true);
    setInterviewResumePersistenceDisabled(false);

    expect(isInterviewResumePersistenceDisabled()).toBe(false);
    savePendingInterview("novel-1", "session-enabled", "location");
    expect(hasPendingInterview("novel-1")).toBe(true);
  });

  it("different novels have separate pending interviews", () => {
    savePendingInterview("novel-1", "session-1", "character");
    savePendingInterview("novel-2", "session-2", "location");

    expect(hasPendingInterview("novel-1")).toBe(true);
    expect(hasPendingInterview("novel-2")).toBe(true);

    expect(getPendingInterview("novel-1")!.sessionId).toBe("session-1");
    expect(getPendingInterview("novel-2")!.sessionId).toBe("session-2");
  });
});
