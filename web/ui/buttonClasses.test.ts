/**
 * Button's class matrix, pinned cell by cell: the composed string is
 * asserted whole with `toBe`, so a variant losing any part — a hover fill,
 * a brightness step, the outline reset — fails here, not in a screenshot.
 * Behaviour (hover/focus/disabled in a real browser) is the E2E/axe
 * suites' job.
 *
 * Ghost's hover restores `text-foreground`: muted text on the `--soft`
 * fill is below AA (4.43:1 light, P1 review R12). Icon keeps muted —
 * glyphs are non-text (3:1) and muted on `--soft` clears that.
 */
import { describe, expect, it } from "vitest";

import { BUTTON_SIZES, BUTTON_VARIANTS, buttonClass, type ButtonProps } from "./Button";

const MATRIX: Record<
  (typeof BUTTON_VARIANTS)[number],
  Record<(typeof BUTTON_SIZES)[number], string>
> = {
  primary: {
    md: "bg-primary text-primary-foreground hover:brightness-95 active:brightness-90 rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 h-7 px-2.5 text-body",
    sm: "bg-primary text-primary-foreground hover:brightness-95 active:brightness-90 rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 h-6 px-2 text-label",
  },
  secondary: {
    md: "border border-border bg-card hover:bg-soft rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 h-7 px-2.5 text-body",
    sm: "border border-border bg-card hover:bg-soft rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 h-6 px-2 text-label",
  },
  ghost: {
    md: "text-muted hover:bg-soft hover:text-foreground rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 h-7 px-2.5 text-body",
    sm: "text-muted hover:bg-soft hover:text-foreground rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 h-6 px-2 text-label",
  },
  icon: {
    md: "grid place-items-center text-muted hover:bg-soft rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 h-7 px-2.5 text-body",
    sm: "grid place-items-center text-muted hover:bg-soft rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 h-6 px-2 text-label",
  },
};

describe("buttonClass", () => {
  it("carries exactly the pinned string in every cell of the matrix", () => {
    for (const variant of BUTTON_VARIANTS) {
      for (const size of BUTTON_SIZES) {
        expect(buttonClass(variant, size)).toBe(MATRIX[variant][size]);
      }
    }
  });

  it("never uses the legacy text-sm or rounded-md vocabulary", () => {
    for (const variant of BUTTON_VARIANTS) {
      for (const size of BUTTON_SIZES) {
        const classes = buttonClass(variant, size);
        expect(classes).not.toContain("text-sm");
        expect(classes).not.toContain("rounded-md");
      }
    }
  });

  it("demands an accessible name for an icon button even with no glyph", () => {
    // @ts-expect-error — `variant: "icon"` without `label` must not typecheck
    const nameless: ButtonProps = { variant: "icon" };
    void nameless;
  });
});
