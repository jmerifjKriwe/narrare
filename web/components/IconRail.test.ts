// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { areaStyle } from "./IconRail";

describe("the rail's area hues", () => {
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
