"use client";

import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { useCallback } from "react";

interface LanguageOption {
  code: string;
  flag: string;
  label: string;
}

const LANGUAGES: LanguageOption[] = [
  { code: "de", flag: "\u{1F1E9}\u{1F1EA}", label: "Deutsch" },
  { code: "en", flag: "\u{1F1EC}\u{1F1E7}", label: "English" },
  { code: "fr", flag: "\u{1F1EB}\u{1F1F7}", label: "Fran\u00E7ais" },
];

export function LanguageSwitcher() {
  const currentLocale = useLocale();
  const router = useRouter();

  const handleChange = useCallback(
    (locale: string) => {
      // biome-ignore lint/suspicious/noDocumentCookie: synchronous cookie needed before router.refresh()
      document.cookie = `NEXT_LOCALE=${locale};path=/;max-age=${60 * 60 * 24 * 365};sameSite=lax`;
      router.refresh();
    },
    [router],
  );

  return (
    <div className="flex items-center">
      <select
        value={currentLocale}
        onChange={(e) => handleChange(e.target.value)}
        aria-label="Language"
        className="appearance-none bg-card/80 backdrop-blur-sm border border-border rounded-full px-3 py-1.5 pr-7 text-xs text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors cursor-pointer focus:outline-none focus:ring-1 focus:ring-primary"
      >
        {LANGUAGES.map(({ code, flag, label }) => (
          <option key={code} value={code}>
            {flag} {label}
          </option>
        ))}
      </select>
    </div>
  );
}
