import { locales, type Locale } from "./generated/catalogs";

/**
 * The language the app speaks, and where that decision came from.
 *
 * Three sources, in this order: the user's stored choice (the server row), the
 * browser's languages, the catalog's source language. One module owns the state
 * so the message function and the switcher can never disagree about it.
 *
 * Nothing here talks to the API: the boot reads the row and calls
 * `adoptServerLocale`, the switcher calls `applyLocale` and persists the answer
 * itself. Keeping the store free of requests is what makes it readable in a
 * test without a network.
 */

const known = new Set<string>(locales);

/** The fallback when no browser language is in the catalog: the source one. */
const SOURCE: Locale = locales[0];

function isKnown(tag: string | null | undefined): tag is Locale {
  return tag !== null && tag !== undefined && known.has(tag);
}

/** The first of the browser's languages the catalog carries, if any. */
function fromBrowser(): Locale | null {
  if (typeof navigator === "undefined") return null;
  const tags = navigator.languages ?? (navigator.language ? [navigator.language] : []);
  for (const tag of tags) {
    // "de-AT" and "de" are the same catalog: match on the primary subtag.
    const base = tag.split("-")[0]?.toLowerCase() ?? "";
    if (isKnown(base)) return base;
  }
  return null;
}

let chosen: Locale | null = null;
let active: Locale = fromBrowser() ?? SOURCE;
const listeners = new Set<() => void>();

function announce(next: Locale): void {
  active = next;
  // The document language is what screen readers and hyphenation read: it must
  // follow the rendered text, not the browser's preference.
  if (typeof document !== "undefined") {
    document.documentElement.lang = next;
  }
  for (const listener of listeners) listener();
}

/** The language `t()` renders in. */
export function activeLocale(): Locale {
  return active;
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
  announce(chosen ?? fromBrowser() ?? SOURCE);
}

/**
 * A choice made in the UI, applied immediately. Persisting it is the caller's
 * job: it knows what to do when the write is refused.
 */
export function applyLocale(locale: Locale | null): void {
  chosen = locale;
  announce(locale ?? fromBrowser() ?? SOURCE);
}

export type { Locale };
