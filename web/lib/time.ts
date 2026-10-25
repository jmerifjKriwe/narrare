import { activeLocale } from "./locale";

/**
 * A last-touched stamp in the reader's own words — "gestern", "yesterday",
 * "hier" — chosen by Intl.RelativeTimeFormat in the active locale. The
 * wording is the platform's, so no catalog carries it and every language the
 * app can switch to is covered without a new key.
 * `timestamp` must be parseable by Date.parse; an invalid timestamp raises RangeError.
 */
export function formatRelative(timestamp: string): string {
  const formatter = new Intl.RelativeTimeFormat(activeLocale(), { numeric: "auto" });
  // Each step covers one unit's span and divides into the next coarser one,
  // so a book touched 90 minutes ago still reads in minutes and drifts into
  // hours only once an hour has actually passed.
  const steps: ReadonlyArray<readonly [Intl.RelativeTimeFormatUnit, number]> = [
    ["second", 60],
    ["minute", 60],
    ["hour", 24],
    ["day", 31],
    ["month", 12],
  ];
  let value = (Date.parse(timestamp) - Date.now()) / 1000;
  for (const [unit, span] of steps) {
    if (Math.abs(value) < span) return formatter.format(Math.round(value), unit);
    value /= span;
  }
  return formatter.format(Math.round(value), "year");
}
