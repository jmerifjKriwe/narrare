"use client";

import { useTranslations } from "next-intl";
import { useThemeStore } from "@/lib/stores/themeStore";
import { cn } from "@/lib/utils";
import type { ColorMode } from "@/lib/stores/themeStore";

const COLOR_MODES: { value: ColorMode; labelKey: string; descriptionKey: string; previewBg: string; previewBorder: string }[] = [
  { value: "light", labelKey: "light", descriptionKey: "lightDesc", previewBg: "bg-[#f8f8f7]", previewBorder: "border-[#2c2c2c]/30" },
  { value: "dark", labelKey: "dark", descriptionKey: "darkDesc", previewBg: "bg-[#0a0a0a]", previewBorder: "border-[#fafafa]/30" },
  { value: "system", labelKey: "system", descriptionKey: "systemDesc", previewBg: "bg-gradient-to-br from-[#f8f8f7] to-[#0a0a0a]", previewBorder: "border-[#525252]/30" },
];

export default function AppearanceSettingsPage() {
  const t = useTranslations("settings-appearance");
  const { colorMode, setColorMode } = useThemeStore();

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold mb-2">{t("title")}</h1>
        <p className="text-muted-foreground">{t("description")}</p>
      </div>

      <div className="grid gap-6">
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
          <h3 className="text-lg font-semibold mb-4">{t("colorMode")}</h3>
          <div className="grid grid-cols-3 gap-4">
            {COLOR_MODES.map((mode) => (
              <button
                key={mode.value}
                type="button"
                onClick={() => setColorMode(mode.value)}
                className={cn(
                  "flex flex-col text-left p-4 rounded-xl border-2 transition-all duration-200 w-full",
                  colorMode === mode.value
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/40",
                )}
              >
                <div className={cn("w-full h-24 rounded-md mb-4 border", mode.previewBg, mode.previewBorder)} />
                <div className="font-medium text-foreground">{t(mode.labelKey)}</div>
                <div className="text-sm text-muted-foreground mt-1">{t(mode.descriptionKey)}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
