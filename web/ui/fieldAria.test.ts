/**
 * The invalid-state attribute a field's control carries, pinned as data:
 * `aria-invalid` exactly when an error is shown, omitted otherwise. The
 * announced error (`role="alert"`) and this attribute are the pair screen
 * readers expect; rendering is the E2E suites' job.
 */
import { describe, expect, it } from "vitest";

import { fieldAria } from "./field";

describe("fieldAria", () => {
  it("names the field invalid exactly when an error is shown", () => {
    expect(fieldAria("required")).toEqual({ "aria-invalid": true });
    expect(fieldAria(undefined)).toEqual({});
  });
});
