import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

const namespaces = [
  "common",
  "auth",
  "wizard",
  "dashboard",
  "editor",
  "errors",
  "settings",
  "settings-ai",
] as const;

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;

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
