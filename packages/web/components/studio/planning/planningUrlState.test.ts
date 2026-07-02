import { describe, expect, it } from "vitest";
import { parsePlanningUrlState, serializePlanningUrlState } from "./planningUrlState";

describe("planning URL state", () => {
  it("parses open timeline state", () => {
    expect(parsePlanningUrlState(new URLSearchParams("planning=1&planningTab=timeline"))).toEqual({
      open: true,
      tab: "timeline",
    });
  });
  it("keeps default collapsed state out of the URL", () => {
    expect(serializePlanningUrlState({ open: false, tab: "storyboard" }).toString()).toBe("");
  });
});
