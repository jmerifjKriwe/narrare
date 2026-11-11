// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { AREA_ICON } from "@shell/lib/area";
import { nav } from "@shell/lib/generated/capabilities";

import { areaStyle, RAIL_GROUPS } from "./IconRail";

describe("the rail's area hues", () => {
  it("maps the five areas to five distinct utilities", () => {
    expect(Object.keys(AREA_ICON).sort()).toEqual([
      "chat",
      "knowledge",
      "planning",
      "settings",
      "writing",
    ]);
    expect(new Set(Object.values(AREA_ICON)).size).toBe(5);
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

  it("keeps a token for each of the five existing areas", () => {
    const css = readFileSync(new URL("../globals.css", import.meta.url), "utf8");
    for (const area of ["writing", "knowledge", "chat", "planning", "settings"]) {
      expect(css).toContain(`--area-${area}:`);
    }
  });
});

describe("the rail's drafted chrome", () => {
  const source = readFileSync(new URL("./IconRail.tsx", import.meta.url), "utf8");

  it("sits on the panel ground behind a hairline edge, flat (Tier 1)", () => {
    // The tier's discipline: a chrome rail is a flat panel bound by the
    // hairline — the open rail's overlay shadow the old shell wore is
    // gone, because elevation belongs to the tiers that earn it.
    expect(source).toMatch(/border-r border-border bg-panel/);
    expect(source).not.toMatch(/shadow-/);
  });

  it("carries the eyebrow-tracked group labels the drafts group the rail by", () => {
    // The section label rides the eyebrow step and the same reveal the
    // destination names ride — one mechanism, so the labels can never
    // open on a different trigger than the names they sit above.
    expect(source).toMatch(/text-eyebrow uppercase/);
    expect(source).toMatch(/const REVEAL =/);
    expect(source.match(new RegExp("\\$\\{REVEAL\\}", "g"))?.length).toBeGreaterThanOrEqual(2);
  });
});

describe("the rail's groups", () => {
  it("place every generated destination exactly once, Home in exactly one", () => {
    // A capability that joins `nav` without being placed in a group
    // fails here: the grouping is a decision the drafts made, not a
    // default the generated file carries.
    const placed = RAIL_GROUPS.flatMap((group) => group.ids).sort();
    expect(placed).toEqual([...nav.map((entry) => entry.id)].sort());
    expect(new Set(placed).size).toBe(placed.length);
    expect(RAIL_GROUPS.filter((group) => group.home)).toHaveLength(1);
  });

  it("names each group through the catalogs, never a hard-coded string", () => {
    for (const group of RAIL_GROUPS) {
      expect(group.labelKey).toMatch(/^shell\.railGroup/);
    }
  });
});

