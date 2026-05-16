"use client";

import { Moon, Sun, BookOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useThemeStore } from "@/lib/stores/themeStore";

/** Resolve whether the UI currently renders in dark mode. */
function useIsDark() {
  const colorMode = useThemeStore((s) => s.colorMode);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    if (colorMode === "dark") {
      setIsDark(true);
    } else if (colorMode === "light") {
      setIsDark(false);
    } else {
      setIsDark(window.matchMedia("(prefers-color-scheme: dark)").matches);
    }
  }, [colorMode]);

  return isDark;
}

export function GeneralSettings() {
  const t = useTranslations("settings");
  const setColorMode = useThemeStore((s) => s.setColorMode);
  const isDark = useIsDark();

  const handleToggleDarkMode = () => {
    setColorMode(isDark ? "light" : "dark");
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl mb-2">{t("general")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("generalDescription")}
        </p>
      </div>

      <div className="space-y-4">
        {/* Dark mode toggle card */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                {isDark ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="mb-1 font-medium">{t("darkMode")}</h3>
                <p className="text-sm text-muted-foreground">
                  {t("darkModeDescription")}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleToggleDarkMode}
              className={`relative w-14 h-8 rounded-full transition-colors ${
                isDark ? "bg-primary" : "bg-muted"
              }`}
              aria-label={t("darkMode")}
            >
              <div
                className={`absolute top-1 w-6 h-6 bg-white rounded-full shadow-sm transition-transform ${
                  isDark ? "translate-x-7" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </div>

        {/* Language selection card */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
              <BookOpen className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h3 className="mb-1 font-medium">{t("languageLabel")}</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {t("languageDescription")}
              </p>
              <select
                className="px-4 py-2 bg-background border border-border rounded-md focus:ring-1 focus:ring-ring transition-shadow"
                defaultValue="de"
                aria-label={t("languageLabel")}
              >
                <option value="de">Deutsch</option>
                <option value="en">English</option>
                <option value="fr">Français</option>
                <option value="es">Español</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
