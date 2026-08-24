/**
 * NoteScopeSelect — scopeToParams unit tests (follow-up P-FE3).
 *
 * The helper is the ONE scope→params mapping shared by the filtered notes
 * list AND the semantic-search body; these tests pin its contract so the
 * two callers can never drift apart again.
 */

import { describe, expect, it } from "vitest";
import { scopeToParams } from "../NoteScopeSelect";

describe("scopeToParams", () => {
  it("maps a null scope (All) to no scope params", () => {
    expect(scopeToParams(null)).toEqual({});
  });

  it("maps a novel scope onto novel_id only", () => {
    expect(scopeToParams({ kind: "novel", id: "nv-1" })).toEqual({ novel_id: "nv-1" });
  });

  it("maps a series scope onto series_id only", () => {
    expect(scopeToParams({ kind: "series", id: "sr-1" })).toEqual({ series_id: "sr-1" });
  });
});
