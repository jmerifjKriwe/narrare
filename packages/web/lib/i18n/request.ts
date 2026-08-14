import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { type Formality, mergeOverlay } from "./mergeOverlay";
import { routing } from "./routing";

const namespaces = [
  "common",
  "auth",
  "wizard",
  "dashboard",
  "editor",
  "errors",
  "export",
  "generation",
  "settings",
  "settings-ai",
  "settings-appearance",
  "studio",
  "analysis",
  "timeline",
  "adaptive",
  "dialogueCoach",
  "aiAssist",
] as const;

export default getRequestConfig(async ({ requestLocale }) => {
  // Priority: cookie > requestLocale > default
  let locale: string | undefined;
  // Formality register (Feature Spec I-Copy-001): default informal. Read in
  // the same cookie store as the locale below.
  let formality: Formality = "informal";

  // 1. Check NEXT_LOCALE cookie (set by user in Settings)
  try {
    const cookieStore = await cookies();
    const cookieLocale = cookieStore.get("NEXT_LOCALE")?.value;
    if (cookieLocale && routing.locales.includes(cookieLocale as "en" | "de" | "fr")) {
      locale = cookieLocale;
    }
    // NEXT_FORMALITY cookie (set by the FormalitySwitcher). Only the two
    // documented values are honoured; anything else falls back to "informal".
    const cookieFormality = cookieStore.get("NEXT_FORMALITY")?.value;
    if (cookieFormality === "formal" || cookieFormality === "informal") {
      formality = cookieFormality;
    }
  } catch {
    // cookies() not available in some contexts (e.g., static generation)
  }

  // 2. Fall back to requestLocale from URL routing / middleware
  if (!locale) {
    locale = await requestLocale;
  }

  // 3. Fall back to default
  if (!locale || !routing.locales.includes(locale as "en" | "de" | "fr")) {
    locale = routing.defaultLocale;
  }

  const messages: Record<string, unknown> = {};
  for (const ns of namespaces) {
    const mod = await import(`../../../i18n/messages/${locale}/${ns}.json`);
    messages[ns] = mod.default;
  }

  // Formality overlay (UI-copy-only, RULE-02 boundary): when the user picked
  // the formal register and the locale actually has a du/Sie distinction
  // (everything except en), deep-merge the sparse formal overlay over the base.
  // English is byte-identical in both registers — no overlay, ever.
  if (formality === "formal" && locale !== "en") {
    try {
      const overlay = (await import(`../../../i18n/overlays/formality/${locale}.json`))
        .default as Record<string, unknown>;
      return { locale, messages: mergeOverlay(messages, overlay) };
    } catch {
      // No overlay authored for this locale yet → fall through to base messages.
    }
  }

  return { locale, messages };
});
