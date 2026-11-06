// @vitest-environment node
import { describe, expect, it } from "vitest";
import { AREA_ICON } from "./IconRail";

describe("the rail's area hues", () => {
  it("maps the four areas to four distinct utilities", () => {
    expect(Object.keys(AREA_ICON).sort()).toEqual(["chat", "knowledge", "settings", "writing"]);
    expect(new Set(Object.values(AREA_ICON)).size).toBe(4);
  });
});
