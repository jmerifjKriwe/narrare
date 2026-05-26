import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

const namespaces = [
  "common",
  "auth",
  "wizard",
  "dashboard",
  "editor",
  "errors",
  "generation",
  "settings",
  "settings-ai",
  "settings-appearance",
  "studio",
  "analysis",
] as const;

export default getRequestConfig(async ({ requestLocale }) => {
  // Priority: cookie > requestLocale > default
  let locale: string | undefined;

  // 1. Check NEXT_LOCALE cookie (set by user in Settings)
  try {
    const cookieStore = await cookies();
    const cookieLocale = cookieStore.get("NEXT_LOCALE")?.value;
    if (cookieLocale && routing.locales.includes(cookieLocale as "en" | "de" | "fr")) {
      locale = cookieLocale;
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

  return { locale, messages };
});
