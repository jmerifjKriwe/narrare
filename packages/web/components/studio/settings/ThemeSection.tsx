"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ColorMode, ThemeName } from "@/lib/stores/themeStore";
import { useThemeStore } from "@/lib/stores/themeStore";

const COLOR_MODES: { value: ColorMode; icon: typeof Sun; labelKey: string }[] = [
  { value: "light", icon: Sun, labelKey: "settings.generalSection.themeLight" },
  { value: "dark", icon: Moon, labelKey: "settings.generalSection.themeDark" },
  { value: "system", icon: Monitor, labelKey: "settings.generalSection.themeSystem" },
];

const THEME_NAMES: { value: ThemeName; label: string }[] = [
  { value: "neutral", label: "Neutral" },
  { value: "narrare", label: "Narrare" },
];

export function ThemeSection() {
  const t = useTranslations("studio");
  const themeStore = useThemeStore();

  return (
    <>
      {/* Color mode toggle */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
            <Sun className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-medium">{t("settings.generalSection.theme")}</h3>
            <p className="text-sm text-muted-foreground">
              {t("settings.generalSection.themeDescription")}
            </p>
          </div>
        </div>
        <div className="flex gap-2 ml-15">
          {COLOR_MODES.map(({ value, icon: Icon, labelKey }) => {
            const isActive = themeStore.colorMode === value;
            return (
              <button
                type="button"
                key={value}
                onClick={() => themeStore.setColorMode(value)}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "bg-muted hover:bg-accent"
                }`}
                aria-label={t(labelKey)}
              >
                <Icon className="w-4 h-4" />
                <span>{t(labelKey)}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Theme selector */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
            <Moon className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-medium">{t("settings.generalSection.themeSelect")}</h3>
            <p className="text-sm text-muted-foreground">
              {t("settings.generalSection.themeSelectDescription")}
            </p>
          </div>
        </div>
        <div className="flex gap-3 ml-15">
          {THEME_NAMES.map(({ value, label }) => {
            const isActive = themeStore.theme === value;
            return (
              <button
                type="button"
                key={value}
                onClick={() => themeStore.setTheme(value)}
                className={`px-6 py-3 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "bg-muted border border-border hover:bg-accent"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}
