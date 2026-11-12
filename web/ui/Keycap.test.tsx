// @vitest-environment jsdom
/**
 * The keycap's contract: a physical key named as one (`<kbd>`), wearing
 * the drafted shell — the card's ground, the hairline edge, the 4 px
 * small-control radius, the meta step and the muted ink (spec §6.5). The
 * badge is a hint, not a control: no elevation and no fill but the card's,
 * because the border discipline keeps decorative box shadows off anything
 * that is not a tier. The shell is pinned whole so a drift fails here,
 * not in a screenshot; the palette's and the ghost-text trailer's
 * renderings consume the primitive later (Task 12).
 */
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Keycap } from "./Keycap";

afterEach(cleanup);

describe("Keycap", () => {
  it("renders a kbd element carrying the key's label", () => {
    const { container } = render(<Keycap>Esc</Keycap>);
    const kbd = container.querySelector("kbd");
    expect(kbd).not.toBeNull();
    expect(kbd?.textContent).toBe("Esc");
  });

  it("wears the drafted shell, pinned whole", () => {
    const { container } = render(<Keycap>K</Keycap>);
    expect(container.querySelector("kbd")?.className).toBe(
      "inline-flex items-center rounded-[var(--radius-sm)] border border-border bg-card px-1.5 py-0.5 text-meta leading-none text-muted",
    );
  });

  it("stays a hint: no elevation, no fill but the card's, no primary", () => {
    const { container } = render(<Keycap>Tab</Keycap>);
    const classes = container.querySelector("kbd")?.className ?? "";
    expect(classes).not.toContain("shadow");
    expect(classes).not.toContain("bg-soft");
    expect(classes).not.toContain("bg-primary");
  });
});
