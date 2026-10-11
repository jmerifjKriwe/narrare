import { describe, expect, it } from "vitest";
import { parsePlanningUrlState, serializePlanningUrlState } from "./planningUrlState";

describe("planning URL state", () => {
  it("parses open timeline state", () => {
    expect(parsePlanningUrlState(new URLSearchParams("planning=1&planningTab=timeline"))).toEqual({
      open: true,
      tab: "timeline",
    });
  });
  it("parses the scenes tab state", () => {
    expect(parsePlanningUrlState(new URLSearchParams("planning=1&planningTab=scenes"))).toEqual({
      open: true,
      tab: "scenes",
    });
  });
  it("serializes the scenes tab state", () => {
    expect(serializePlanningUrlState({ open: true, tab: "scenes" }).toString()).toBe(
      "planning=1&planningTab=scenes",
    );
  });
  it("keeps default collapsed state out of the URL", () => {
    expect(serializePlanningUrlState({ open: false, tab: "storyboard" }).toString()).toBe("");
  });
});
