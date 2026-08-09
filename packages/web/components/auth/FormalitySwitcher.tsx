"use client";

import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { Formality } from "@/lib/i18n/mergeOverlay";

/**
 * Formality register switcher (Feature Spec I-Copy-001).
 *
 * Mirrors the {@link LanguageSwitcher} pattern exactly: writes the choice to a
 * cookie synchronously, then calls `router.refresh()` so the loader
 * (`lib/i18n/request.ts`) re-reads `NEXT_FORMALITY` and deep-merges the formal
 * overlay. next-intl and every call site stay unaware of the merge.
 *
 * Cookie-only persistence for v1 (no backend / no migration) — that is why this
 * control lives alongside the cookie-based LanguageSwitcher on auth screens,
 * not in the studio Settings (whose language control is API-backed).
 *
 * RULE-02 boundary: this affects UI copy only; it never reaches core/prompts/.
 */

/** Cookie name — matches the read site in `lib/i18n/request.ts`. */
const NEXT_FORMALITY_COOKIE = "NEXT_FORMALITY";

/** One year, matching the locale cookie lifetime. */
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

/**
 * Register labels per locale. These are the linguistic register names
 * themselves (fixed terms), not translatable copy — mirroring the locale
 * switcher, which hardcodes "Deutsch" / "English" / "Français".
 */
const LABELS: Record<"de" | "fr", { ariaLabel: string; informal: string; formal: string }> = {
  de: { ariaLabel: "Anrede", informal: "Du", formal: "Sie" },
  fr: { ariaLabel: "Formule d'adresse", informal: "tu", formal: "vous" },
};

export function FormalitySwitcher() {
  const currentLocale = useLocale();
  const router = useRouter();
  const [formality, setFormality] = useState<Formality>("informal");

  // Read the persisted choice after mount. document.cookie is client-only, so
  // reading it in an effect (not during render) avoids an SSR/cookie hydration
  // mismatch.
  useEffect(() => {
    const match = document.cookie.match(/(?:^|; )NEXT_FORMALITY=(informal|formal)\b/);
    if (match) {
      setFormality(match[1] as Formality);
    }
  }, []);

  const handleChange = useCallback(
    (next: Formality) => {
      // biome-ignore lint/suspicious/noDocumentCookie: synchronous cookie needed before router.refresh()
      document.cookie = `${NEXT_FORMALITY_COOKIE}=${next};path=/;max-age=${COOKIE_MAX_AGE};sameSite=lax`;
      setFormality(next);
      router.refresh();
    },
    [router],
  );

  // English has no du/Sie distinction (en is byte-identical in both registers).
  // Hide the control for en so users never see a no-op switch.
  if (currentLocale === "en") {
    return null;
  }

  const labels = LABELS[currentLocale as "de" | "fr"] ?? LABELS.de;

  return (
    <select
      value={formality}
      onChange={(e) => handleChange(e.target.value as Formality)}
      aria-label={labels.ariaLabel}
      className="appearance-none bg-card/80 backdrop-blur-sm border border-border rounded-full px-3 py-1.5 pr-7 text-xs text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors cursor-pointer focus:outline-none focus:ring-1 focus:ring-primary"
    >
      <option value="informal">{labels.informal}</option>
      <option value="formal">{labels.formal}</option>
    </select>
  );
}
