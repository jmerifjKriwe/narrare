/**
 * Button's class matrix, pinned cell by cell: the composed string is
 * asserted whole with `toBe`, so a variant losing any part — a hover fill,
 * an opacity step, the outline reset — fails here, not in a screenshot.
 * Behaviour (hover/focus/disabled in a real browser) is the E2E/axe
 * suites' job.
 *
 * The matrix is the drafted ladder (spec §6.5): three heights — 28 px
 * (dense floor), 36 px, 40 px — on the control radius, with the amber focus
 * ring and its 1 px offset on every cell, and five paints. The icon button
 * is the drafted square instead: the glyph plus 6 px of padding, on the
 * small radius, and no horizontal padding from the ladder.
 *
 * The ring's offset is transparent: Tailwind's offset colour is white by
 * default, which on the dark theme is a white seam around the amber ring
 * instead of a gap in the surface.
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
    sm: "bg-primary text-primary-foreground shadow-sm hover:opacity-95 active:opacity-90 rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-7 text-label px-2.5",
    md: "bg-primary text-primary-foreground shadow-sm hover:opacity-95 active:opacity-90 rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-9 text-body px-3",
    lg: "bg-primary text-primary-foreground shadow-sm hover:opacity-95 active:opacity-90 rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-10 text-emph px-4",
  },
  secondary: {
    sm: "border border-border bg-card hover:bg-soft rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-7 text-label px-2.5",
    md: "border border-border bg-card hover:bg-soft rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-9 text-body px-3",
    lg: "border border-border bg-card hover:bg-soft rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-10 text-emph px-4",
  },
  ghost: {
    sm: "text-muted hover:bg-soft hover:text-foreground rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-7 text-label px-2.5",
    md: "text-muted hover:bg-soft hover:text-foreground rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-9 text-body px-3",
    lg: "text-muted hover:bg-soft hover:text-foreground rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-10 text-emph px-4",
  },
  destructive: {
    sm: "border border-danger text-danger hover:bg-danger/10 rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-7 text-label px-2.5",
    md: "border border-danger text-danger hover:bg-danger/10 rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-9 text-body px-3",
    lg: "border border-danger text-danger hover:bg-danger/10 rounded-[var(--radius-control)] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-10 text-emph px-4",
  },
  icon: {
    sm: "grid place-items-center text-muted hover:bg-soft rounded-[var(--radius-sm)] p-1.5 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-7 text-label",
    md: "grid place-items-center text-muted hover:bg-soft rounded-[var(--radius-sm)] p-1.5 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-9 text-body",
    lg: "grid place-items-center text-muted hover:bg-soft rounded-[var(--radius-sm)] p-1.5 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50 h-10 text-emph",
  },
};

describe("the button matrix", () => {
  it("names the five paints and the three heights", () => {
    expect([...BUTTON_VARIANTS]).toEqual([
      "primary",
      "secondary",
      "ghost",
      "destructive",
      "icon",
    ]);
    expect([...BUTTON_SIZES]).toEqual(["sm", "md", "lg"]);
  });

  it("carries exactly the pinned string in every cell of the matrix", () => {
    for (const variant of BUTTON_VARIANTS) {
      for (const size of BUTTON_SIZES) {
        expect(buttonClass(variant, size)).toBe(MATRIX[variant][size]);
      }
    }
  });

  it("wears the ladder's radius names, never the legacy aliases", () => {
    for (const variant of BUTTON_VARIANTS) {
      for (const size of BUTTON_SIZES) {
        const classes = buttonClass(variant, size);
        expect(classes).not.toContain("rounded-[var(--radius)]");
        expect(classes).not.toContain("rounded-[var(--radius-lg)]");
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

  it("pads the icon button with its glyph, not with the ladder's inset", () => {
    for (const size of BUTTON_SIZES) {
      const classes = buttonClass("icon", size);
      expect(classes).toContain("p-1.5");
      expect(classes).toContain("rounded-[var(--radius-sm)]");
      expect(classes).not.toContain("px-");
    }
  });

  it("demands an accessible name for an icon button even with no glyph", () => {
    // @ts-expect-error — `variant: "icon"` without `label` must not typecheck
    const nameless: ButtonProps = { variant: "icon" };
    void nameless;
  });
});
