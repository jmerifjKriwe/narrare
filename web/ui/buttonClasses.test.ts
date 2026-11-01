/**
 * Button's class matrix, pinned as data: every cell keeps the one focus
 * treatment, keeps off the legacy `text-sm`/`rounded-md` vocabulary the
 * token scale replaces, and carries exactly the fill its variant name
 * promises. Behaviour (hover/focus/disabled in a real browser) is the
 * E2E/axe suites' job — this test holds the contract later surfaces compose
 * against, so a drifted class string fails here and not in a screenshot.
 *
 * The ghost hover restores `text-foreground`: muted text on the `--soft`
 * fill is below AA (4.43:1 light, P1 review R12).
 */
import { describe, expect, it } from "vitest";

import { BUTTON_SIZES, BUTTON_VARIANTS, buttonClass } from "./Button";

describe("buttonClass", () => {
  it("keeps the shared focus ring in every variant and size", () => {
    for (const variant of BUTTON_VARIANTS) {
      for (const size of BUTTON_SIZES) {
        const classes = buttonClass(variant, size);
        expect(classes).toContain("focus-visible:ring-2");
        expect(classes).toContain("focus-visible:ring-focus");
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

  it("paints primary with the primary fill and its foreground text", () => {
    expect(buttonClass("primary", "md")).toContain(
      "bg-primary text-primary-foreground",
    );
  });

  it("keeps secondary, ghost and icon off the primary fill", () => {
    for (const variant of ["secondary", "ghost", "icon"] as const) {
      expect(buttonClass(variant, "md")).not.toContain("bg-primary");
    }
  });

  it("sizes md to 28px and sm to 24px", () => {
    expect(buttonClass("primary", "md")).toContain("h-7");
    expect(buttonClass("primary", "sm")).toContain("h-6");
  });

  it("carries the shared disabled and radius treatment", () => {
    for (const variant of BUTTON_VARIANTS) {
      for (const size of BUTTON_SIZES) {
        const classes = buttonClass(variant, size);
        expect(classes).toContain("rounded-[var(--radius)]");
        expect(classes).toContain("disabled:opacity-50");
      }
    }
  });

  it("restores foreground text on ghost's soft hover fill (AA on --soft)", () => {
    expect(buttonClass("ghost", "md")).toContain("hover:text-foreground");
  });

  it("matches the size strings exactly", () => {
    expect(buttonClass("secondary", "md")).toContain("h-7 px-2.5 text-body");
    expect(buttonClass("secondary", "sm")).toContain("h-6 px-2 text-label");
  });
});
