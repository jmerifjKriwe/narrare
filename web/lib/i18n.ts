import IntlMessageFormat from "intl-messageformat";
import { useSyncExternalStore } from "react";

import { catalogs } from "./generated/catalogs";
import { activeLocale, subscribeLocale, type Locale } from "./locale";

/**
 * The key union comes from the source catalog, so a typo or a key that exists
 * in no locale is a compile error at the call site. The catalogs themselves are
 * generated from `i18n/*.json`; a locale missing a key is a compile error at the
 * generated assignment.
 */
export type MessageKey = keyof typeof catalogs.en;

// Messages are ICU: `{name}`, `{count, plural, …}`, `{kind, select, …}`. A
// formatter is built once per locale and key — parsing on every render would
// repeat work the message never changes. The language is part of the cache key,
// so switching it cannot serve the previous language's formatter.
const formatters = new Map<string, IntlMessageFormat>();

export function t(key: MessageKey, params?: Record<string, string | number>): string {
  const locale: Locale = activeLocale();
  const message = catalogs[locale][key];
  // No parameters: the message is its own rendering, no parser involved.
  if (params === undefined) return message;

  const cached = `${locale}\u0000${key}`;
  let formatter = formatters.get(cached);
  if (formatter === undefined) {
    formatter = new IntlMessageFormat(message, locale);
    formatters.set(cached, formatter);
  }
  return String(formatter.format(params));
}

/**
 * The `t` for components: subscribing here is what makes a language change
 * re-render the page that shows the words. `t` itself stays a plain function,
 * because it is also called outside React (the document title, tests).
 */
export function useTranslation(): typeof t {
  useSyncExternalStore(subscribeLocale, activeLocale, activeLocale);
  return t;
}
