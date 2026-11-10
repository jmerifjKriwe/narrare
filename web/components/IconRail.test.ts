// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { AREA_ICON } from "@shell/lib/area";

import { areaStyle } from "./IconRail";

describe("the rail's area hues", () => {
  it("maps the four areas to four distinct utilities", () => {
    expect(Object.keys(AREA_ICON).sort()).toEqual(["chat", "knowledge", "settings", "writing"]);
    expect(new Set(Object.values(AREA_ICON)).size).toBe(4);
  });

  it("applies the hue to the icon's span", () => {
    // The constant alone would pass while the link stopped wearing it; the
    // four hues would collapse to the rail's muted ink unnoticed.
    const source = readFileSync(new URL("./IconRail.tsx", import.meta.url), "utf8");
    expect(source).toMatch(/<span style=\{areaStyle\(area\)\}>/);
  });

  it("derives the colour from any capability id", () => {
    expect(areaStyle("future-area")).toEqual({
      color: "var(--area-future-area, var(--foreground))",
    });
  });

  it("keeps a token for each of the four existing areas", () => {
    const css = readFileSync(new URL("../globals.css", import.meta.url), "utf8");
    for (const area of ["writing", "knowledge", "chat", "settings"]) {
      expect(css).toContain(`--area-${area}:`);
    }
  });
});
