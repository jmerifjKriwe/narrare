import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "de", "fr"] as const,
  defaultLocale: "en",
});
