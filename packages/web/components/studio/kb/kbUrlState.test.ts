import { describe, expect, it } from "vitest";
import { EMPTY_KB_SEARCH_QUERY, parseKBUrlState, serializeKBUrlState } from "./kbUrlState";

describe("KB URL state", () => {
  it("parses type mode search and entry", () => {
    expect(
      parseKBUrlState(new URLSearchParams("type=character&mode=detail&entry=e1&q=ada")),
    ).toEqual({
      type: "character",
      mode: "detail",
      entryId: "e1",
      query: "ada",
    });
  });
  it("normalizes invalid mode to detail", () => {
    expect(parseKBUrlState(new URLSearchParams("mode=unknown"))).toMatchObject({ mode: "detail" });
  });
  it("uses the non-visible empty search query default when q is absent", () => {
    expect(parseKBUrlState(new URLSearchParams()).query).toBe(EMPTY_KB_SEARCH_QUERY);
  });
  it("removes default detail mode on serialize", () => {
    expect(
      serializeKBUrlState({ type: null, mode: "detail", entryId: null, query: "" }).toString(),
    ).toBe("");
  });
});
