import { locales, type Locale } from "@shell/lib/generated/catalogs";

/**
 * The language choice before setup — the welcome screen's and the wizard's.
 * Shell-owned since the language contract extracted (D17, #892): the one
 * home in `language.tsx` reads and writes this mirror for every pre-setup
 * face, and the provisioning seam carries it into the fresh row.
 *
 * The settings row is the record once it exists, but the row is created by
 * setup itself: `PATCH /api/settings` refuses with 409 "setup required"
 * until then (settings/service.py), and the welcome screen exists precisely
 * in that state. The switcher still has to work — a control that snaps back
 * on the only screen that shows it is broken — so the choice lives in the
 * browser until the row can hold it, the formality module's own shape
 * (web/lib/formality.ts): applied at once, remembered locally, adopted on
 * the next visit. The write through the settings API is still attempted;
 * the structural 409 keeps the mirror, a success clears it (the row is the
 * record from then on), any other refusal restores the prior choice.
 *
 * The provisioning seam carries the mirrored choice into the fresh row and
 * clears the mirror when that write lands; a refused carry-over keeps the
 * mirror, so the choice is not lost. The boot reads the mirror only while the
 * row holds no choice, and a stored choice always wins: a mirror a failed
 * carry-over left behind can never override the row's language.
 */

const STORAGE_KEY = "narrare.locale.preSetup";

const known = new Set<string>(locales);

/** The mirrored choice, or null when none stands; an unknown value is ignored. */
export function readPreSetupLocale(): Locale | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored !== null && known.has(stored) ? (stored as Locale) : null;
  } catch {
    // A blocked store costs the memory, never the choice on screen.
    return null;
  }
}

/** Remember the choice that stands; null clears the mirror. */
export function storePreSetupLocale(locale: Locale | null): void {
  if (typeof localStorage === "undefined") return;
  try {
    if (locale === null) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // As above: the applied locale is the truth the reader sees.
  }
}
