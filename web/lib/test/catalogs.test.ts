import { describe, expect, it } from "vitest";

import { catalogFor, isLoaded } from "../catalog";
import { locales } from "../generated/catalogs";
import { merged } from "./catalogs";

describe("the catalog test bed", () => {
  it("holds every language before a test runs", () => {
    for (const code of locales) {
      expect(isLoaded(code), code).toBe(true);
      expect(catalogFor(code), code).toBe(merged[code]);
    }
  });
});
