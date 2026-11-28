import { isLoaded, loadCatalog, registerCatalogReset } from "./catalog";
import { locales, type Locale } from "./generated/catalogs";

/**
 * The language the app speaks, where that decision came from, and the tag it
 * formats by.
 *
 * Three sources, in this order: the user's stored choice (the server row), the
 * browser's languages, the catalog's source language. One module owns the state
 * so the message function and the switcher can never disagree about it.
 *
 * A browser tag is not a catalog code: `de-AT` is served by the `de` catalog,
 * and `zh-Hans-CN` by `zh-Hans`. The matcher maps a tag onto its catalog
 * without ever handing the tag to `Intl` unexamined — an unknown tag must not
 * silently resolve to the machine's own locale — while the matched tag is kept
 * whole, region included, so dates and numbers read the reader's regional
 * face.
 *
 * Nothing here talks to the API: the boot reads the row and calls
 * `adoptServerLocale`, the switcher calls `applyLocale` and persists the answer
 * itself. Keeping the store free of requests is what makes it readable in a
 * test without a network.
 */

const known = new Set<string>(locales);

/** The fallback when no browser language is in the catalog: the source one. */
const SOURCE: Locale = locales[0];

/** The matched catalog and the tag `Intl` formats by. */
export type ResolvedLocale = Readonly<{ catalog: Locale; formatLocale: string }>;

function source(): ResolvedLocale {
  return { catalog: SOURCE, formatLocale: SOURCE };
}

function isKnown(tag: string | null | undefined): tag is Locale {
  return tag !== null && tag !== undefined && known.has(tag);
}

/** The canonical spelling of a tag, or `null` when `Intl` refuses it. */
function canonicalTag(tag: string | null | undefined): string | null {
  if (tag === null || tag === undefined) return null;
  try {
    const [canonical] = Intl.getCanonicalLocales(tag);
    return canonical ?? null;
  } catch {
    return null;
  }
}

/** A tag's language and its script, if it names one; `null` when malformed. */
function subtags(tag: string): Readonly<{ language: string; script: string | null }> | null {
  try {
    const locale = new Intl.Locale(tag);
    return { language: locale.language.toLowerCase(), script: locale.script ?? null };
  } catch {
    return null;
  }
}

/**
 * The registry language a tag maps onto, or `null`.
 *
 * The order is resolution's own: the exact code first, then the same language
 * and the same script, then — only for a tag that names no script — the same
 * language, an unscripted registry code before a scripted one. A tag whose
 * script the registry does not carry matches nothing: `zh-Hant` must not be
 * served `zh-Hans` text. Ill-formed and empty tags match nothing, and no input
 * throws.
 */
export function matchLocale(tag: string | null | undefined): Locale | null {
  const canonical = canonicalTag(tag);
  if (canonical === null) return null;
  const wanted = subtags(canonical);
  if (wanted === null) return null;

  // The exact code — `Intl` has already normalised the case.
  const exact = locales.find((code) => code.toLowerCase() === canonical.toLowerCase());
  if (exact !== undefined) return exact;

  if (wanted.script !== null) {
    // The same language and the same script: a longer tag keeps its region,
    // never its script when the registry has no such catalog.
    return (
      locales.find((code) => {
        const candidate = subtags(code);
        return (
          candidate !== null &&
          candidate.language === wanted.language &&
          candidate.script === wanted.script
        );
      }) ?? null
    );
  }

  // No script named: the same language, an unscripted code before a scripted
  // one (registry order decides inside each group).
  const sameLanguage = locales.filter((code) => subtags(code)?.language === wanted.language);
  return sameLanguage.find((code) => subtags(code)?.script === null) ?? sameLanguage[0] ?? null;
}

/**
 * The catalog a tag resolves to and the tag to format by. A region is kept:
 * `de-AT` reads `de` and formats `de-AT`. A tag that maps onto nothing — an
 * unknown code, a script the registry lacks, an ill-formed or empty tag —
 * resolves to the source language, never to the machine's own locale.
 */
export function resolveLocale(tag: string | null | undefined): ResolvedLocale {
  const canonical = canonicalTag(tag);
  if (canonical === null) return source();
  const catalog = matchLocale(canonical);
  if (catalog === null) return source();
  return { catalog, formatLocale: canonical };
}

/** The browser's languages in its own order, or none when there is no browser. */
function browserTags(): readonly string[] {
  if (typeof navigator === "undefined") return [];
  return navigator.languages ?? (navigator.language ? [navigator.language] : []);
}

/** The first of the browser's languages the catalog carries, with its tag. */
function fromBrowser(): ResolvedLocale | null {
  for (const tag of browserTags()) {
    const catalog = matchLocale(tag);
    if (catalog === null) continue;
    return { catalog, formatLocale: canonicalTag(tag) ?? catalog };
  }
  return null;
}

/** The tag a chosen catalog formats by: the browser's own when it speaks it. */
function formatTagFor(catalog: Locale): string {
  for (const tag of browserTags()) {
    if (matchLocale(tag) === catalog) return canonicalTag(tag) ?? catalog;
  }
  return catalog;
}

let chosen: Locale | null = null;

// The invariant's floor: before its first adoption the app speaks the source
// catalog — the only language the store holds at init — never the browser's,
// whose catalog is not here yet. `activeLocale()` is a loaded catalog from
// module init on, so no face can be announced without its own words.
let active: Locale = SOURCE;
let activeFormat: string = SOURCE;
const listeners = new Set<() => void>();

// The document language is what screen readers and hyphenation read: it must
// follow the rendered text, not the browser's preference. At init that text is
// the source's, so the tag is too.
if (typeof document !== "undefined") {
  document.documentElement.lang = SOURCE;
}

// The latest catalog call, shared by the boot's hydration and a switch: a
// load that lands after a newer call still fills the store, but activates
// nothing. Without it a reader who picks two languages quickly would end up
// in the first one once its chunk arrives.
let latestActivation = 0;

// The boot's own ordering, beside the shared number: every hydration takes
// one, so a hydration of an already-held target can retire an older
// hydration without taking the number a switch in flight owns.
let latestHydration = 0;

function announce(resolved: ResolvedLocale): void {
  // No face is announced without its own words: a catalog the store does not
  // hold is answered by the source — the catalog and the tag the boot's own
  // source fallback uses — so `activeLocale()` is always a loaded catalog,
  // whichever caller asked.
  const spoken = isLoaded(resolved.catalog)
    ? resolved
    : { catalog: SOURCE, formatLocale: formatTagFor(SOURCE) };
  active = spoken.catalog;
  activeFormat = spoken.formatLocale;
  // The document language is what screen readers and hyphenation read: it must
  // follow the rendered text, not the browser's preference.
  if (typeof document !== "undefined") {
    document.documentElement.lang = spoken.catalog;
  }
  for (const listener of listeners) listener();
}

/** The language `t()` renders in. */
export function activeLocale(): Locale {
  return active;
}

/** The tag `Intl` formats by: the active catalog, carrying its region. */
export function activeFormatLocale(): string {
  return activeFormat;
}

/** The stored choice, or `null` when the browser decides. */
export function chosenLocale(): Locale | null {
  return chosen;
}

export function subscribeLocale(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The row's value, as the boot read it. A code outside the catalog is ignored. */
export function adoptServerLocale(locale: string | null): void {
  chosen = isKnown(locale) ? locale : null;
  const resolved =
    chosen !== null
      ? { catalog: chosen, formatLocale: formatTagFor(chosen) }
      : (fromBrowser() ?? source());
  // A row that names a language this session never loaded is recorded, never
  // spoken: the face keeps the loaded language it has (announcing the source
  // would repaint the page while the row's catalog is on its way), and the
  // boot's hydration reveals the row's language once it lands.
  if (isLoaded(resolved.catalog)) announce(resolved);
}

/**
 * The language a choice would make active: the code itself, or the browser's
 * language for `null`, or the source when the browser speaks none of them.
 */
export function targetLocale(locale: Locale | null): Locale {
  return locale ?? fromBrowser()?.catalog ?? SOURCE;
}

/**
 * A choice made in the UI, applied immediately when its catalog is in the
 * store. Persisting it is the caller's job: it knows what to do when the
 * write is refused. A language whose catalog is not here is still recorded as
 * the choice — the row, the mirror and `chosen` are the record — but the
 * source language answers: no face is announced without its own words, so the
 * restore after a refused write cannot paint a half-translated language.
 */
export function applyLocale(locale: Locale | null): void {
  const resolved =
    locale !== null
      ? { catalog: locale, formatLocale: formatTagFor(locale) }
      : (fromBrowser() ?? source());
  chosen = locale;
  // `announce` answers the source for a catalog the store does not hold: the
  // choice stays recorded, and no missing language is ever spoken.
  announce(resolved);
}

/**
 * Announces a catalog the store already holds, without touching the stored
 * choice: the boot's hydration makes the row's or the browser's language
 * active, and only a choice writes `chosen`.
 */
function reveal(locale: Locale): void {
  announce({ catalog: locale, formatLocale: formatTagFor(locale) });
}

// A store reset (the test bed's) drops every catalog but the source. A face
// still wearing one of the dropped languages would read the source's words
// under that tag — and a parameterized sentence would cache a source
// formatter under its key — so the reset answers the source at once.
registerCatalogReset(() => {
  if (!isLoaded(active)) reveal(SOURCE);
});

/**
 * The boot's one async edge: loads `target`'s catalog before the first paint.
 * A chunk that cannot be fetched is logged and the source language answers,
 * so the page never renders half translated; the call never rejects. A newer
 * call supersedes this one — the load still fills the store, nothing is
 * announced.
 *
 * A target that is already the active language and in the store returns at
 * once, taking no number from the shared counter: a settings change that
 * changes nothing must not supersede a switch in flight. It still moves the
 * hydration's own number, so an older hydration's late landing cannot reveal
 * over this newer decision.
 */
export async function hydrateLocale(target: Locale): Promise<void> {
  const hydration = ++latestHydration;
  if (target === active && isLoaded(target)) return;
  const call = ++latestActivation;
  try {
    await loadCatalog(target);
  } catch (error) {
    console.error(`[i18n] the ${target} catalog could not be loaded`, error);
    if (call === latestActivation && hydration === latestHydration) reveal(SOURCE);
    return;
  }
  if (call === latestActivation && hydration === latestHydration) reveal(target);
}

/**
 * A switch: resolves the language that would become active (`null` follows
 * the browser), loads its catalog, then applies it. A failed load keeps the
 * active language and resolves `false`; so does a call a newer one superseded
 * — in both cases nothing was activated, so the caller writes nothing.
 */
export async function activateLocale(locale: Locale | null): Promise<boolean> {
  const target = targetLocale(locale);
  const call = ++latestActivation;
  try {
    await loadCatalog(target);
  } catch {
    return false;
  }
  if (call !== latestActivation) return false;
  applyLocale(locale);
  return true;
}

export type { Locale };
