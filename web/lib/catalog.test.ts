import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { catalogFor, isLoaded, loadCatalog, resetCatalogs, setCatalog } from "./catalog";
import { catalogLoaders } from "./generated/catalogs";
import { activeLocale, applyLocale } from "./locale";
import { en, merged } from "./test/catalogs";

/**
 * The contract the shell reads through: a language always has a catalog and a
 * load happens once per language, however many callers ask at the same time.
 * The bed's `en` is the generated source catalog, so these assertions pin the
 * store's starting point without a copy of the words.
 */
describe("the catalog store", () => {
  const generatedLoaders = { ...catalogLoaders };

  beforeEach(() => {
    resetCatalogs();
  });

  afterEach(() => {
    Object.assign(catalogLoaders, generatedLoaders);
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

  it("reads the map's source entry for a language that is not loaded", () => {
    // One truth: the map, not the eager table. A source catalog put in the
    // store is what every unloaded language reads, and the source's own
    // load answers it too.
    const replaced = { ...en, "nav.back": "Zurück" };
    setCatalog("en", replaced);

    expect(catalogFor("de")).toBe(replaced);
    expect(isLoaded("de")).toBe(false);
  });

  it("answers the source's own load from the map, not the eager table", async () => {
    const replaced = { ...en, "nav.back": "Zurück" };
    setCatalog("en", replaced);

    await expect(loadCatalog("en")).resolves.toBe(replaced);
  });

  it("a reset that drops the active language returns the face to the source", async () => {
    await loadCatalog("de");
    applyLocale("de");
    expect(activeLocale()).toBe("de");

    resetCatalogs();

    // The reset reseeded only the source: a face left on the dropped German
    // would read the source's words under `de` and cache them under its key.
    expect(activeLocale()).toBe("en");
    expect(isLoaded(activeLocale())).toBe(true);
  });

  it("a load in flight when the store resets lands in nothing", async () => {
    await loadCatalog("fr");
    applyLocale("fr");
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const realDe = catalogLoaders.de;
    catalogLoaders.de = async () => {
      await gate;
      return realDe();
    };

    const inFlight = loadCatalog("de");
    resetCatalogs();
    release();
    await inFlight;

    // The store the load belonged to is gone: its module may still arrive,
    // but it fills nothing — and the face has returned to the source.
    expect(isLoaded("de")).toBe(false);
    expect(catalogFor("de")).toBe(en);
    expect(activeLocale()).toBe("en");
    expect(isLoaded(activeLocale())).toBe(true);
  });

  it("calls a language's loader once for two parallel loads", async () => {
    let calls = 0;
    const realFr = catalogLoaders.fr;
    catalogLoaders.fr = async () => {
      calls += 1;
      return realFr();
    };

    const [first, second] = await Promise.all([loadCatalog("fr"), loadCatalog("fr")]);

    expect(calls).toBe(1);
    expect(first).toBe(second);
  });

  it("calls the loader again after a failed load, and resolves", async () => {
    let calls = 0;
    const realFr = catalogLoaders.fr;
    catalogLoaders.fr = async () => {
      calls += 1;
      if (calls === 1) throw new Error("chunk");
      return realFr();
    };

    await expect(loadCatalog("fr")).rejects.toThrow("chunk");
    expect(isLoaded("fr")).toBe(false);

    await expect(loadCatalog("fr")).resolves.toBe(merged.fr);
    expect(calls).toBe(2);
    expect(isLoaded("fr")).toBe(true);
  });
});
