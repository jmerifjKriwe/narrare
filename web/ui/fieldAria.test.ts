/**
 * The field primitives' pure contracts, pinned as data: the invalid-state
 * attribute a control carries, and the control class matrix (the textarea
 * grows from the 28px minimum, the plan's density law). Rendering and
 * wiring are the consumers' E2E suites' job.
 */
import { describe, expect, it } from "vitest";

import { controlClass, fieldAria } from "./field";

describe("fieldAria", () => {
  it("names the field invalid exactly when an error is shown", () => {
    expect(fieldAria("required")).toEqual({ "aria-invalid": true });
    expect(fieldAria(undefined)).toEqual({});
    // An empty string is no error, not an empty alert.
    expect(fieldAria("")).toEqual({});
  });
});

describe("controlClass", () => {
  it("pins input and select to the fixed 28px control", () => {
    expect(controlClass()).toBe(
      "h-7 rounded-[var(--radius)] border border-border bg-card px-2 text-body focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50",
    );
  });

  it("lets the textarea grow from the same 28px minimum", () => {
    expect(controlClass(true)).toBe(
      "min-h-7 rounded-[var(--radius)] border border-border bg-card px-2 text-body focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50",
    );
  });
});
