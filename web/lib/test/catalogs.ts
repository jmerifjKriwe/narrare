import { setCatalog } from "../catalog";
import { catalogs, type Catalog, type CatalogModule, type Locale } from "../generated/catalogs";

/**
 * The test bed: a language's real catalog, read eagerly.
 *
 * A test asserts against the words the reader would see, never against the
 * store's fallback or a hand-written copy, so it keeps passing when a
 * fourth language appears and cannot pass vacuously when a translation is
 * missing. `merged` keys each module by the language it declares, and the
 * source language is seeded from the eager table because no `en` module
 * exists.
 */
const modules = import.meta.glob("../generated/catalogs/*.ts", { eager: true }) as Record<
  string,
  CatalogModule
>;

export const merged: Record<string, Catalog> = Object.fromEntries(
  Object.values(modules).map((module) => [module.locale, module.default]),
);

merged.en = catalogs.en;

export const de = merged.de;
export const en = merged.en;
export const fr = merged.fr;

/**
 * Puts every language's catalog in the store. The setup file calls this once
 * per test file; a test that resets the module registry calls it again after
 * the reset when it needs the preloaded store.
 */
export function preloadCatalogs(): void {
  for (const [code, catalog] of Object.entries(merged)) setCatalog(code as Locale, catalog);
}
