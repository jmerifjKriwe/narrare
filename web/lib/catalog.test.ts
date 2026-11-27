import { beforeEach, describe, expect, it } from "vitest";

import { catalogFor, isLoaded, loadCatalog, resetCatalogs } from "./catalog";
import { en, merged } from "./test/catalogs";

/**
 * The contract the shell reads through: a language always has a catalog and a
 * load happens once per language, however many callers ask at the same time.
 * The bed's `en` is the generated source catalog, so these assertions pin the
 * store's starting point without a copy of the words.
 */
describe("the catalog store", () => {
  beforeEach(() => {
    resetCatalogs();
  });

  it("always has the source catalog", () => {
    expect(catalogFor("en")).toBe(en);
    expect(isLoaded("en")).toBe(true);
  });

  it("reads the source catalog for a language that is not loaded", () => {
    expect(catalogFor("de")).toBe(en);
    expect(isLoaded("de")).toBe(false);
  });

  it("reads a language's own catalog once it is loaded", async () => {
    await loadCatalog("de");
    expect(catalogFor("de")).toBe(merged.de);
    expect(isLoaded("de")).toBe(true);
  });

  it("answers parallel loads of one language with the same catalog", async () => {
    const [first, second] = await Promise.all([loadCatalog("fr"), loadCatalog("fr")]);
    expect(first).toBe(second);
    expect(await loadCatalog("fr")).toBe(first);
  });

  it("loads the source language without a request", async () => {
    expect(await loadCatalog("en")).toBe(en);
  });
});
