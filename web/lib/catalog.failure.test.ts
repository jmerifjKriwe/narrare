import { expect, it, vi } from "vitest";

/**
 * The failure path is its own file because the mock replaces the generated
 * module the store reads its loaders from. The Global Constraints' rule for
 * this bed: reset the module registry, then import what is tested dynamically
 * — the setup file has already evaluated these modules.
 */
vi.mock("./generated/catalogs", async (importOriginal) => {
  const real = await importOriginal<typeof import("./generated/catalogs")>();
  return {
    ...real,
    catalogLoaders: {
      ...real.catalogLoaders,
      de: () => Promise.reject(new Error("chunk")),
    },
  };
});

it("rejects a language whose module cannot be fetched and leaves the store untouched", async () => {
  vi.resetModules();
  const { catalogFor, isLoaded, loadCatalog, resetCatalogs } = await import("./catalog");
  // After the reset the bed re-reads the same module instances the store
  // does, so `en` is the source catalog this fresh store seeded itself with.
  const { en } = await import("./test/catalogs");
  resetCatalogs();
  await expect(loadCatalog("de")).rejects.toThrow("chunk");
  expect(isLoaded("de")).toBe(false);
  expect(catalogFor("de")).toBe(en);
});
