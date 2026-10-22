import IntlMessageFormat from "intl-messageformat";

import { catalogs, type Locale } from "./generated/catalogs";

export type { Locale };

/**
 * The key union comes from the source catalog, so a typo or a key that exists
 * in no locale is a compile error at the call site. The catalogs themselves are
 * generated from `i18n/*.json`; a locale missing a key is a compile error at the
 * generated assignment.
 */
export type MessageKey = keyof typeof catalogs.en;

export const locale: Locale = "de";

// Messages are ICU: `{name}`, `{count, plural, …}`, `{kind, select, …}`. A
// formatter is built once per locale and key — parsing on every render would
// repeat work the message never changes.
const formatters = new Map<string, IntlMessageFormat>();

export function t(key: MessageKey, params?: Record<string, string | number>): string {
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
