// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { AREA_ICON } from "./IconRail";

describe("the rail's area hues", () => {
  it("maps the four areas to four distinct utilities", () => {
    expect(Object.keys(AREA_ICON).sort()).toEqual(["chat", "knowledge", "settings", "writing"]);
    expect(new Set(Object.values(AREA_ICON)).size).toBe(4);
  });

  it("applies the map to the icon's span", () => {
    // The constant alone would pass while the link stopped wearing it; the
    // four hues would collapse to the rail's muted ink unnoticed.
    const source = readFileSync(new URL("./IconRail.tsx", import.meta.url), "utf8");
    expect(source).toMatch(/<span className=\{AREA_ICON\[area\]\}>/);
  });
});
