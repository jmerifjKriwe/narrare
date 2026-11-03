import { describe, expect, it } from "vitest";

import type { KnowledgeDocument } from "@shell/lib/api/client";

import { readDocuments } from "./KnowledgePage";

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
