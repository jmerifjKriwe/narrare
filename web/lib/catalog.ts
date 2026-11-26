import { catalogs, catalogLoaders, locales, type Catalog, type Locale } from "./generated/catalogs";

/**
 * The loaded catalogs, one per language, and one in-flight request per
 * language.
 *
 * A reader needs a catalog before a language module arrives: the first paint,
 * and a switch to a language whose chunk is still loading, read the source
 * catalog rather than an empty page. `catalogFor` therefore never throws and
 * never returns `undefined`; a loaded language reads its own words. The eager
 * `catalogs` table is the source language's home — the other languages live in
 * their own modules, fetched once and stored here.
 */

// The registry's first language is the source one; the tuple keeps the type
// literal, so `locale === SOURCE` narrows the loader index to the languages
// that have a module.
const SOURCE = locales[0];

const loaded = new Map<Locale, Catalog>([[SOURCE, catalogs.en]]);
const loading = new Map<Locale, Promise<Catalog>>();

/** The catalog a language reads now: its own once loaded, else the source. */
export function catalogFor(locale: Locale): Catalog {
  return loaded.get(locale) ?? catalogs.en;
}

/** Whether the language's own catalog is in the store. */
export function isLoaded(locale: Locale): boolean {
  return loaded.has(locale);
}

/** Puts a catalog in the store — the test bed's preload, and a future cache. */
export function setCatalog(locale: Locale, catalog: Catalog): void {
  loaded.set(locale, catalog);
}

/**
 * Resolves a language's catalog, fetching its module at most once: parallel
 * callers share one request, and a second call after the load reads the store.
 * A failed fetch leaves the store untouched and rejects with the loader's
 * error, so the caller decides between the source language and a retry.
 */
export function loadCatalog(locale: Locale): Promise<Catalog> {
  const present = loaded.get(locale);
  if (present !== undefined) return Promise.resolve(present);
  if (locale === SOURCE) return Promise.resolve(catalogs.en);

  const pending = loading.get(locale);
  if (pending !== undefined) return pending;

  const request = catalogLoaders[locale]()
    .then((module) => {
      loaded.set(locale, module.default);
      return module.default;
    })
    .finally(() => {
      loading.delete(locale);
    });

  loading.set(locale, request);
  return request;
}

/**
 * Forgets every catalog but the source one. The tests' starting point, so a
 * test never inherits a language another test loaded.
 */
export function resetCatalogs(): void {
  loaded.clear();
  loaded.set(SOURCE, catalogs.en);
  loading.clear();
}
