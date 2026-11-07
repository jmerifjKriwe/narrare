import { describe, expect, it } from "vitest";

import type { KnowledgeDocument } from "@shell/lib/api/client";

import { formatBytes, readDocuments } from "./KnowledgePage";

/**
 * The documents read goes through one seam, and the seam decides what the
 * page may claim: an answer that is not "ok" is `failed` — never an empty
 * list, because "no documents" is a fact only a reachable service can
 * claim (F14). An ok answer with no data is honestly empty; an ok answer
 * with data passes the rows through untouched.
 */
describe("readDocuments", () => {
  it("refuses to answer an outage with an empty list", () => {
    expect(readDocuments({ response: { ok: false } })).toEqual({ kind: "failed" });
  });

  it("reads an ok answer without data as honestly empty", () => {
    expect(readDocuments({ response: { ok: true } })).toEqual({
      kind: "ok",
      documents: [],
    });
  });

  it("passes the rows of an ok answer through untouched", () => {
    const row = { id: "d1", title: "Notizen", created_at: "2026-11-03T10:00:00Z" };
    expect(readDocuments({ data: [row as KnowledgeDocument], response: { ok: true } })).toEqual({
      kind: "ok",
      documents: [row],
    });
  });
});

/**
 * A size the row predates is unknown, and unknown is not "0 B" — the
 * helper answers `null` and the row renders no size slot at all. A known
 * size reads on the decimal ladder the 1 MB upload limit itself speaks,
 * with one decimal past the unit: the limit's own edge reads "1.0 MB",
 * not "1000 kB" and not "1 MB" worn as an exact count it is not.
 */
describe("formatBytes", () => {
  it("answers null for a size the row predates — never a guessed zero", () => {
    expect(formatBytes(null)).toBeNull();
  });

  it("reads plain bytes under a thousand without a unit's decimals", () => {
    expect(formatBytes(512)).toBe("512 B");
  });

  it("steps to kB at a thousand bytes, one decimal along", () => {
    expect(formatBytes(1_536)).toBe("1.5 kB");
  });

  it("rounds 999,999 bytes into the megabyte it already rounds to", () => {
    expect(formatBytes(999_999)).toBe("1.0 MB");
  });

  it("reads the 1 MB upload limit as its own edge: 1.0 MB", () => {
    expect(formatBytes(1_000_000)).toBe("1.0 MB");
  });
});
