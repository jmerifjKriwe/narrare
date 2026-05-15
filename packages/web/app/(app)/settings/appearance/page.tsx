"use client";

import { useTranslations } from "next-intl";
import { useThemeStore } from "@/lib/stores/themeStore";
import { cn } from "@/lib/utils";

export default function AppearanceSettingsPage() {
  const t = useTranslations("settings-appearance");
  const { theme, setTheme } = useThemeStore();

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold mb-2 font-display">{t("title")}</h1>
        <p className="text-muted-foreground">{t("description")}</p>
      </div>

      <div className="grid gap-6">
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
          <h3 className="text-lg font-semibold mb-4">{t("theme")}</h3>
          <div className="grid grid-cols-2 gap-4">
            <ThemeOption
              label={t("themes.pergament")}
              description={t("themes.pergamentDesc")}
              isActive={theme === "pergament"}
              onClick={() => setTheme("pergament")}
              previewClass="bg-[#FAF8F3] border-[#B8621B]/30"
            />
            <ThemeOption
              label={t("themes.neutral")}
              description={t("themes.neutralDesc")}
              isActive={theme === "neutral"}
              onClick={() => setTheme("neutral")}
              previewClass="bg-[#f8f8f7] border-[#2c2c2c]/30"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function ThemeOption({
  label,
  description,
  isActive,
  onClick,
  previewClass,
}: {
  label: string;
  description: string;
  isActive: boolean;
  onClick: () => void;
  previewClass: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-col text-left p-4 rounded-xl border-2 transition-all duration-200 w-full",
        isActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/40",
      )}
    >
      <div className={cn("w-full h-24 rounded-md mb-4 border", previewClass)} />
      <div className="font-medium text-foreground">{label}</div>
      <div className="text-sm text-muted-foreground mt-1">{description}</div>
    </button>
  );
}
