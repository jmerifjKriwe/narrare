// @vitest-environment jsdom
/**
 * The field primitives' contracts, pinned as data: the invalid-state
 * attribute a control carries, the control class matrix (the drafted
 * heights, the control radius and the amber focus ring) and the select's
 * shell — the native control with the app's own chevron beside it. The
 * matrix and the chevron are this wave's produced interface, so they are
 * pinned here; the wiring's behaviour in a real browser is the E2E suites'
 * job.
 */
import { createElement } from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { controlClass, fieldAria, Select } from "./field";
import { Icon } from "./icons";

describe("fieldAria", () => {
  it("names the field invalid exactly when an error is shown", () => {
    expect(fieldAria("required")).toEqual({ "aria-invalid": true });
    expect(fieldAria(undefined)).toEqual({});
    // An empty string is no error, not an empty alert.
    expect(fieldAria("")).toEqual({});
  });
});

/**
 * The control class matrix, cell by cell, asserted whole with `toBe`: a
 * control losing the radius, the ring or its offset fails here, not in a
 * screenshot. The heights are the drafted shells (spec §6.5) — 36 px by
 * default, the 32 px compact rung — on the 8 px control radius, with the
 * button ladder's amber ring and its 1 px gap.
 */
const MATRIX = {
  default:
    "h-9 rounded-[var(--radius-control)] border border-border bg-card px-2 text-body focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50",
  compact:
    "h-8 rounded-[var(--radius-control)] border border-border bg-card px-2 text-body focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50",
  grows:
    "min-h-9 rounded-[var(--radius-control)] border border-border bg-card px-2 text-body focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50",
  growsCompact:
    "min-h-8 rounded-[var(--radius-control)] border border-border bg-card px-2 text-body focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50",
} as const;

/**
 * The select's own string: the control contract plus the three
 * companions of the custom chevron — the native arrow off, the room the
 * chevron needs on the right, the width the shell fills — and the `peer`
 * that lets the chevron dim with a disabled control.
 */
const SELECT_SHELL = `${MATRIX.default} peer w-full appearance-none pr-8`;

describe("controlClass", () => {
  it("pins the default control to the drafted 36px shell", () => {
    expect(controlClass()).toBe(MATRIX.default);
  });

  it("offers the compact rung at 32px", () => {
    expect(controlClass({ size: "compact" })).toBe(MATRIX.compact);
  });

  it("lets the textarea grow from the same height", () => {
    expect(controlClass({ grows: true })).toBe(MATRIX.grows);
    expect(controlClass({ grows: true, size: "compact" })).toBe(MATRIX.growsCompact);
  });

  it("wears the control radius and the amber ring, never the legacy aliases", () => {
    for (const classes of Object.values(MATRIX)) {
      expect(classes).toContain("rounded-[var(--radius-control)]");
      expect(classes).not.toContain("rounded-[var(--radius)]");
      expect(classes).not.toContain("rounded-md");
      expect(classes).toContain("focus-visible:ring-2");
      expect(classes).toContain("focus-visible:ring-focus");
      expect(classes).toContain("focus-visible:ring-offset-1");
      expect(classes).toContain("focus-visible:ring-offset-transparent");
      // The field's own voice is the body step — never the legacy `text-sm`.
      expect(classes).toContain("text-body");
      expect(classes).not.toContain("text-sm");
    }
  });
});

describe("the select's shell", () => {
  afterEach(cleanup);

  /** The select the primitive renders, with one option in it. */
  function shell(): HTMLElement {
    const { container } = render(
      createElement(
        Select,
        { name: "locale" },
        createElement("option", { value: "en" }, "English"),
      ),
    );
    return container;
  }

  it("keeps the native control — the popup stays the browser's own", () => {
    const control = shell().querySelector("select");
    expect(control).not.toBeNull();
    expect(control?.getAttribute("name")).toBe("locale");
    // The native arrow is off; the app's own chevron replaces it.
    expect(control?.className).toBe(SELECT_SHELL);
  });

  it("draws the icon set's select chevron beside the control", () => {
    const drawn = shell().querySelector("svg path")?.getAttribute("d");
    const chevron = render(createElement(Icon, { name: "selectChevron" })).container
      .querySelector("svg path")
      ?.getAttribute("d");
    expect(drawn).toBe(chevron);
    expect(drawn).toBeTruthy();
  });
});
