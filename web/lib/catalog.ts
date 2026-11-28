import { catalogs, catalogLoaders, locales, type Catalog, type Locale } from "./generated/catalogs";

/**
 * The loaded catalogs, one per language, and one in-flight request per
 * language.
 *
 * A reader needs a catalog before a language module arrives: the first paint,
 * and a switch to a language whose chunk is still loading, read the source
 * catalog rather than an empty page. `catalogFor` therefore never throws and
 * never returns `undefined`; a loaded language reads its own words.
 *
 * The map is the one truth. The eager `catalogs` table seeds it at init and at
 * reset — it is the source language's home, the only language bundled — and is
 * read nowhere else: an unloaded language reads the map's source entry, so a
 * source catalog put in the store (`setCatalog`) is what every unloaded
 * language sees, and the source's own load answers it too.
 */

// The registry's first language is the source one; the tuple keeps the type
// literal, so `locale === SOURCE` narrows the loader index to the languages
// that have a module.
const SOURCE = locales[0];

const loaded = new Map<Locale, Catalog>([[SOURCE, catalogs[SOURCE]]]);
const loading = new Map<Locale, Promise<Catalog>>();

/**
 * The store's generation. A reset moves it: a load begun in an older
 * generation still resolves for its caller, but it belongs to the store the
 * reset replaced and fills nothing. Without this, a module that lands after
 * the reset would put a language back into a store that had already forgotten
 * it, and the next test would inherit it.
 */
let generation = 0;

/**
 * The language state's answer to a reset. It is registered from `locale.ts`
 * — the store must not import the state that reads it — and called after the
 * map has been reseeded: a reset that dropped the active language would
 * otherwise leave the face on a catalog the store no longer holds, which the
 * invariant forbids.
 */
let onReset: (() => void) | null = null;

/** Registers the reset response; the language state owns the only one. */
export function registerCatalogReset(listener: () => void): void {
  onReset = listener;
}

/** The source entry the map always holds — seeded at init and at every reset. */
function sourceCatalog(): Catalog {
  return loaded.get(SOURCE)!;
}

/** The catalog a language reads now: its own once loaded, else the source. */
export function catalogFor(locale: Locale): Catalog {
  return loaded.get(locale) ?? sourceCatalog();
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
  if (locale === SOURCE) return Promise.resolve(sourceCatalog());

  const pending = loading.get(locale);
  if (pending !== undefined) return pending;

  const begun = generation;
  const request = catalogLoaders[locale]()
    .then((module) => {
      if (begun === generation) loaded.set(locale, module.default);
      return module.default;
    })
    .finally(() => {
      // Only the generation that installed the promise may clear it: a
      // reset (or a newer generation's load) owns the entry now.
      if (begun === generation) loading.delete(locale);
    });

  loading.set(locale, request);
  return request;
}

/**
 * Forgets every catalog but the source one. The tests' starting point, so a
 * test never inherits a language another test loaded, and the one place the
 * generation moves: a load that lands afterwards fills nothing. The language
 * state is told afterwards — a face left on a dropped language is answered by
 * the source, so the invariant holds across the reset too.
 */
export function resetCatalogs(): void {
  generation += 1;
  loaded.clear();
  loaded.set(SOURCE, catalogs[SOURCE]);
  loading.clear();
  onReset?.();
}
