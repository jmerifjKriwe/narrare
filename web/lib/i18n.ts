import IntlMessageFormat from "intl-messageformat";
import { useSyncExternalStore } from "react";

import { formattingLocale } from "./format";
import { activeFormality, subscribeFormality } from "./formality";
import { catalogs } from "./generated/catalogs";
import { overlays } from "./generated/overlays";
import { activeLocale, subscribeLocale, type Locale } from "./locale";

/**
 * The key union comes from the source catalog, so a typo or a key that exists
 * in no locale is a compile error at the call site. The catalogs themselves are
 * generated from `i18n/*.json` and each capability's `web/i18n/*.json`; a locale
 * missing a key is a compile error at the generated assignment. A formal
 * register reads its sparse overlay first and falls through to the base.
 */
export type MessageKey = keyof typeof catalogs.en;

// Messages are ICU: `{name}`, `{count, plural, …}`, `{kind, select, …}`. A
// formatter is built once per locale, register and key — parsing on every
// render would repeat work the message never changes. Both choices are part of
// the cache key, so switching either cannot serve the previous formatter.
const formatters = new Map<string, IntlMessageFormat>();

export function t(key: MessageKey, params?: Record<string, string | number>): string {
  const locale: Locale = activeLocale();
  const formality = activeFormality();
  const message =
    formality === "formal" && locale !== "en"
      ? (overlays[locale]?.[key] ?? catalogs[locale][key])
      : catalogs[locale][key];
  // No parameters: the message is its own rendering, no parser involved.
  if (params === undefined) return message;

  const formatLocale = formattingLocale();
  const cached = `${formatLocale}\u0000${formality}\u0000${key}`;
  let formatter = formatters.get(cached);
  if (formatter === undefined) {
    formatter = new IntlMessageFormat(message, formatLocale);
    formatters.set(cached, formatter);
  }
  return String(formatter.format(params));
}

/**
 * The `t` for components: subscribing here is what makes a language or
 * register change re-render the page that shows the words. `t` itself stays a
 * plain function, because it is also called outside React (the document title,
 * tests).
 */
export function useTranslation(): typeof t {
  useSyncExternalStore(subscribeLocale, activeLocale, activeLocale);
  useSyncExternalStore(subscribeFormality, activeFormality, activeFormality);
  return t;
}
