import { afterEach, beforeEach, expect, it, vi } from "vitest";

import type { Locale } from "./generated/catalogs";

/**
 * A catalog that cannot be fetched: the first paint falls back to the source
 * language, a switch keeps the language it had, and the latest of two
 * overlapping choices wins. The store itself is real; only its loader answers
 * a test-controlled result for `fr`. The Global Constraints' rule for this
 * bed: reset the module registry, then import what is tested dynamically —
 * the setup file has already evaluated these modules.
 */
const control = vi.hoisted(() => ({
  failFr: true,
  releaseFr: null as (() => void) | null,
}));

vi.mock("./catalog", async (importOriginal) => {
  const real = await importOriginal<typeof import("./catalog")>();
  return {
    ...real,
    loadCatalog: async (locale: Locale) => {
      if (locale === "fr") {
        if (control.failFr) throw new Error("chunk");
        await new Promise<void>((resolve) => {
          control.releaseFr = resolve;
        });
      }
      return real.loadCatalog(locale);
    },
  };
});

beforeEach(() => {
  control.failFr = true;
  control.releaseFr = null;
  // The fallback is expected to be loud; the assertion below reads the spy.
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(async () => {
  // A held load cannot be cancelled: release it and let it settle so its late
  // landing cannot undo the next test's reset.
  control.releaseFr?.();
  control.releaseFr = null;
  await Promise.resolve();
  await Promise.resolve();
  vi.restoreAllMocks();
});

it("falls back to the source language when the first paint's catalog cannot be fetched", async () => {
  vi.resetModules();
  const { activeLocale, applyLocale, hydrateLocale } = await import("./locale");
  const { resetCatalogs } = await import("./catalog");
  resetCatalogs();
  applyLocale("en");
  await expect(hydrateLocale("fr")).resolves.toBeUndefined();
  expect(activeLocale()).toBe("en");
  expect(console.error).toHaveBeenCalled();
});

it("keeps the active language when a switch's catalog cannot be fetched", async () => {
  vi.resetModules();
  const { activateLocale, activeLocale, applyLocale } = await import("./locale");
  const { loadCatalog } = await import("./catalog");
  // `applyLocale` never announces a language without its catalog: the
  // German catalog is put in the store first, as the boot's hydration does.
  await loadCatalog("de");
  applyLocale("de");
  await expect(activateLocale("fr")).resolves.toBe(false);
  expect(activeLocale()).toBe("de");
  await expect(activateLocale("de")).resolves.toBe(true);
  expect(activeLocale()).toBe("de");
});

it("only the latest of two overlapping choices becomes active", async () => {
  vi.resetModules();
  const { activateLocale, activeLocale, applyLocale } = await import("./locale");
  const { isLoaded, loadCatalog } = await import("./catalog");
  control.failFr = false;
  // `applyLocale` never announces a language without its catalog: the
  // German catalog is put in the store first, as the boot's hydration does.
  await loadCatalog("de");
  applyLocale("de");

  const first = activateLocale("fr");
  await expect(activateLocale("en")).resolves.toBe(true);
  expect(activeLocale()).toBe("en");

  control.releaseFr?.();
  await expect(first).resolves.toBe(false);
  expect(activeLocale()).toBe("en");
  expect(isLoaded("fr")).toBe(true);
});
