/**
 * The row's and the panel's class contracts, pinned whole: `rowClass` is
 * the one string both the plain `Row` and the React-Aria `GridList.Item`
 * consumers wear, and `panelClass` / `panelHeaderClass` are the panel's
 * measure (§8.3: 10 px dense, 12 px regular) — so a lost rule border, a
 * sneaking legacy token or a drifted density fails here, not in a
 * screenshot. Behaviour (selection in a real browser, the keyboard walk,
 * the axe pass) is the E2E suites' job.
 *
 * L2, binding since P1's review: selection is the `--soft` wash, weight
 * 600 and a 2 px `--primary` inset edge, with foreground text — muted on
 * the wash is below AA (4.43:1 light), and a filled `bg-primary` block is
 * the look this primitive replaces.
 */
import { describe, expect, it } from "vitest";

import { panelClass, panelHeaderClass } from "./Panel";
import { rowClass } from "./Row";

const ROW_BASE =
  "group h-7 flex w-full items-center gap-2 px-3 text-left text-body border-b border-rule hover:bg-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";
const ROW_FLUSH =
  "group h-7 flex w-full items-center gap-2 text-left text-body border-b border-rule hover:bg-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";
const SELECTED_ADDITIONS =
  "bg-soft font-semibold shadow-[inset_2px_0_0_var(--primary)]";

describe("rowClass", () => {
  it("carries exactly the pinned string, unselected and selected", () => {
    expect(rowClass(false)).toBe(ROW_BASE);
    expect(rowClass(true)).toBe(`${ROW_BASE} ${SELECTED_ADDITIONS}`);
  });

  it("keeps the row height, fills its container, answers the pointer and never wears the legacy vocabulary", () => {
    for (const selected of [false, true]) {
      const classes = rowClass(selected);
      expect(classes).toContain("h-7");
      expect(classes).toContain("w-full");
      expect(classes).toContain("text-left");
      expect(classes).toContain("hover:bg-soft");
      expect(classes).not.toContain("bg-primary");
      expect(classes).not.toContain("text-primary-foreground");
      expect(classes).not.toContain("rounded-md");
      expect(classes).not.toContain("border-border");
      expect(classes).not.toContain("text-sm");
    }
  });

  it("selects by adding the wash, the weight and the edge marker, nothing else", () => {
    // Selected is the base plus exactly the L2 additions — no hidden swap
    // of text colour or shape rides along with the state.
    expect(rowClass(true)).toBe(`${rowClass(false)} ${SELECTED_ADDITIONS}`);
  });

  it("drops its own gutter when the surface around it owns one", () => {
    // A row inside a padded dock or panel body must not add a second inset
    // to the text it shares a column with (the heading above it).
    expect(rowClass(false, true)).toBe(ROW_FLUSH);
    expect(rowClass(true, true)).toBe(`${ROW_FLUSH} ${SELECTED_ADDITIONS}`);
  });
});

describe("panelClass", () => {
  it("keeps the §8.3 measure: 10 px dense, 12 px regular", () => {
    expect(panelClass(true)).toBe("p-2.5");
    expect(panelClass(false)).toBe("p-3");
  });

  it("lays the header out on the rule, with room for the actions at the far edge", () => {
    expect(panelHeaderClass()).toBe(
      "flex items-center gap-2 border-b border-rule px-3 py-2",
    );
    // A dense body sits at 10 px; its header must not sit at 12.
    expect(panelHeaderClass(true)).toBe(
      "flex items-center gap-2 border-b border-rule px-2.5 py-2",
    );
  });
});
