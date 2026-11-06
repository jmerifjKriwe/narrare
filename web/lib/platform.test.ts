// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { isMac } from "./platform";

const original = navigator.userAgent;

afterEach(() => {
  Object.defineProperty(navigator, "userAgent", { value: original, configurable: true });
});

describe("isMac", () => {
  it("reads a Mac agent as a Mac", () => {
    Object.defineProperty(navigator, "userAgent", {
      value: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36",
      configurable: true,
    });
    expect(isMac()).toBe(true);
  });

  it("reads a Linux agent as not a Mac", () => {
    Object.defineProperty(navigator, "userAgent", {
      value: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
      configurable: true,
    });
    expect(isMac()).toBe(false);
  });
});
