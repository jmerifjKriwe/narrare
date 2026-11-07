import { activeLocale } from "./locale";

/**
 * The locale `Intl` formats in: the chosen catalog's language, carrying the
 * browser's regional variant when the two agree.
 *
 * The app speaks one catalog per language (`de`), but a browser in Austria
 * asks for `de-AT`: same words, regional numbers and dates. Taking the
 * browser's tag only when its primary subtag matches the active catalog keeps
 * a deliberate language choice intact — a German UI on an English browser
 * formats as German, not English — while a `de-AT` reader gets `de-AT` dates.
 */
export function formattingLocale(): string {
  const active = activeLocale();
  if (typeof navigator === "undefined") return active;
  const browser = navigator.language;
  if (!browser) return active;
  const base = browser.split("-")[0]?.toLowerCase() ?? "";
  return base === active ? browser : active;
}

/** A date in the reader's regional format; `value` is anything `Date` parses. */
export function formatDate(
  value: string | number | Date,
  options?: Intl.DateTimeFormatOptions,
): string {
  return new Intl.DateTimeFormat(formattingLocale(), options).format(new Date(value));
}

/** A number in the reader's regional format. */
export function formatNumber(
  value: number | bigint,
  options?: Intl.NumberFormatOptions,
): string {
  return new Intl.NumberFormat(formattingLocale(), options).format(value);
}
