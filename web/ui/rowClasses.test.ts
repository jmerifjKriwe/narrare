/**
 * Row's class contract, pinned whole: `rowClass` is the one string both
 * the plain `Row` and the React-Aria `GridList.Item` consumers wear, so a
 * lost rule border or a sneaking legacy token fails here, not in a
 * screenshot. Behaviour (selection in a real browser, the keyboard walk,
 * the axe pass) is the E2E suites' job.
 *
 * L2, binding since P1's review: selection is the `--soft` wash, weight
 * 600 and a 2 px `--primary` inset edge, with foreground text — muted on
 * the wash is below AA (4.43:1 light), and a filled `bg-primary` block is
 * the look this primitive replaces.
 */
import { describe, expect, it } from "vitest";

import { rowClass } from "./Row";

const SELECTED_ADDITIONS =
  "bg-soft font-semibold shadow-[inset_2px_0_0_var(--primary)]";

describe("rowClass", () => {
  it("carries exactly the pinned string, unselected and selected", () => {
    expect(rowClass(false)).toBe(
      "h-7 flex items-center gap-2 px-3 text-body border-b border-rule focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
    );
    expect(rowClass(true)).toBe(
      `h-7 flex items-center gap-2 px-3 text-body border-b border-rule focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${SELECTED_ADDITIONS}`,
    );
  });

  it("keeps the row height and never wears the legacy vocabulary", () => {
    for (const selected of [false, true]) {
      const classes = rowClass(selected);
      expect(classes).toContain("h-7");
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
});
