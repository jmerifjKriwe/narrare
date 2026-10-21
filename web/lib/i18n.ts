import de from "../../i18n/de.json";
import en from "../../i18n/en.json";
import fr from "../../i18n/fr.json";

export type Locale = "en" | "de" | "fr";

// Typing the map against `en` makes a missing key a build error in every locale.
const catalogs: Record<Locale, typeof en> = { en, de, fr };

export const locale: Locale = "de";

export function t(key: keyof typeof en): string {
  return catalogs[locale][key];
}
