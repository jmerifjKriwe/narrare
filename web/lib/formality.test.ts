// @vitest-environment jsdom

import { afterEach, describe, expect, it } from "vitest";

import {
  activeFormality,
  adoptStoredFormality,
  applyFormality,
  subscribeFormality,
} from "./formality";

afterEach(() => {
  applyFormality("informal");
  localStorage.clear();
});

describe("formality", () => {
  it("starts informal", () => {
    expect(activeFormality()).toBe("informal");
  });

  it("announces a change to every subscriber", () => {
    let heard = 0;
    const unsubscribe = subscribeFormality(() => {
      heard += 1;
    });

    applyFormality("formal");
    unsubscribe();
    applyFormality("informal");

    expect(activeFormality()).toBe("informal");
    expect(heard).toBe(1);
  });

  it("persists the choice", () => {
    applyFormality("formal");

    expect(localStorage.getItem("narrare.formality")).toBe("formal");
  });

  it("adopts a stored choice", () => {
    localStorage.setItem("narrare.formality", "formal");

    adoptStoredFormality();

    expect(activeFormality()).toBe("formal");
  });

  it("ignores a stored value that is not a register", () => {
    localStorage.setItem("narrare.formality", "shouty");

    adoptStoredFormality();

    expect(activeFormality()).toBe("informal");
  });
});
