/**
 * The shelf's pure model: which book leads, which follow, and what the
 * progress bar may honestly claim. The rules the page renders are pinned
 * here without a DOM — the hero is the latest-edited unarchived novel, the
 * grid is the rest newest-first, and a book without a target has no
 * percentage at all (the landing's honest neutral, never a guessed goal).
 */
import { describe, expect, it } from "vitest";

import type { Novel } from "@shell/lib/api/client";

import { pickHero, progress, shelfGrid } from "./shelf";

/** A novel row with the fields the model reads; the rest ride defaults. */
function row(id: string, updatedAt: string, extra: Partial<Novel> = {}): Novel {
  return {
    id,
    title: `Buch ${id}`,
    genre: null,
    blurb: null,
    author: null,
    language: null,
    chapter_count: 0,
    word_count: 0,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: updatedAt,
    last_exported_at: null,
    status: null,
    series_title: null,
    series_volume: null,
    archived_at: null,
    target_words: null,
    ...extra,
  };
}

describe("pickHero — the latest-edited unarchived novel leads", () => {
  it("picks the newest updated_at, not the list's first row", () => {
    const older = row("a", "2026-11-10T10:00:00Z");
    const newer = row("b", "2026-11-12T10:00:00Z");
    expect(pickHero([older, newer])?.id).toBe("b");
    expect(pickHero([newer, older])?.id).toBe("b");
  });

  it("compares parsed instants — offsets order as moments, not strings", () => {
    // 12:00+02:00 is 10:00Z, earlier than 11:00Z even though its string
    // sorts later; the hero must follow the moment, not the text.
    const offsetLater = row("a", "2026-11-12T12:00:00+02:00");
    const utcEarlier = row("b", "2026-11-12T11:00:00Z");
    expect(pickHero([offsetLater, utcEarlier])?.id).toBe("b");
  });

  it("skips archived books even when they are the newest", () => {
    const archived = row("a", "2026-11-14T10:00:00Z", {
      archived_at: "2026-11-14T10:00:00Z",
    });
    const active = row("b", "2026-11-12T10:00:00Z");
    expect(pickHero([archived, active])?.id).toBe("b");
    expect(pickHero([archived])).toBeNull();
  });

  it("answers null for an empty shelf", () => {
    expect(pickHero([])).toBeNull();
  });

  it("keeps the first row on an exact tie — the choice stays deterministic", () => {
    const first = row("a", "2026-11-12T10:00:00Z");
    const second = row("b", "2026-11-12T10:00:00Z");
    expect(pickHero([first, second])?.id).toBe("a");
  });
});

describe("shelfGrid — the rest, newest first", () => {
  it("excludes the hero and the archived, and orders by updated_at descending", () => {
    const hero = row("hero", "2026-11-14T10:00:00Z");
    const older = row("old", "2026-11-09T10:00:00Z");
    const newer = row("new", "2026-11-13T10:00:00Z");
    const archived = row("gone", "2026-11-15T10:00:00Z", {
      archived_at: "2026-11-15T10:00:00Z",
    });
    const grid = shelfGrid([hero, older, archived, newer], hero);
    expect(grid.map((novel) => novel.id)).toEqual(["new", "old"]);
  });

  it("is empty when the hero is the only book", () => {
    const hero = row("hero", "2026-11-14T10:00:00Z");
    expect(shelfGrid([hero], hero)).toEqual([]);
    expect(shelfGrid([], null)).toEqual([]);
  });

  it("keeps the list's order on a tie — stable, never a reshuffle", () => {
    const hero = row("hero", "2026-11-14T10:00:00Z");
    const first = row("a", "2026-11-12T10:00:00Z");
    const second = row("b", "2026-11-12T10:00:00Z");
    expect(shelfGrid([hero, first, second], hero).map((novel) => novel.id)).toEqual(["a", "b"]);
  });
});

describe("progress — the bar claims only what the target measures", () => {
  it("is null without a target — no percentage, no sliver", () => {
    expect(progress(48342, null)).toBeNull();
    expect(progress(48342, undefined)).toBeNull();
    expect(progress(0, null)).toBeNull();
  });

  it("refuses a zero or negative target as no target", () => {
    expect(progress(100, 0)).toBeNull();
    expect(progress(100, -5)).toBeNull();
  });

  it("floors the label the way the draft draws it, and keeps the bar exact", () => {
    // The draft's own figures: 3.384/60.000 reads 5% on a 5.6% bar.
    const result = progress(3384, 60000);
    expect(result?.percent).toBe(5);
    expect(result?.width).toBeCloseTo(5.64, 5);
  });

  it("clamps a finished book at 100 — the bar never overflows", () => {
    const result = progress(90000, 65000);
    expect(result?.percent).toBe(100);
    expect(result?.width).toBe(100);
  });

  it("answers zero for an unwritten book with a target", () => {
    const result = progress(0, 50000);
    expect(result?.percent).toBe(0);
    expect(result?.width).toBe(0);
  });
});
