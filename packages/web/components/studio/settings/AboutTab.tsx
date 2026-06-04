import { BookOpen } from "lucide-react";
import { useTranslations } from "next-intl";
import { ABOUT_FEATURE_KEYS } from "./settings-view-config";

export function AboutTab() {
  const t = useTranslations("studio");
  const detailRows = [
    { label: t("settings.aboutSection.version"), value: "0.1.0" },
    { label: t("settings.aboutSection.license"), value: "MIT" },
    { label: t("settings.aboutSection.build"), value: "2026.05" },
  ];

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("settings.aboutSection.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("settings.aboutSection.description")}</p>
      </div>
      <div className="space-y-4">
        {/* App info card */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 rounded-lg bg-primary flex items-center justify-center">
              <BookOpen className="w-6 h-6 text-primary-foreground" />
            </div>
            <div>
              <h3 className="text-lg font-medium">Narrare</h3>
              <p className="text-sm text-muted-foreground">
                {t("settings.aboutSection.descriptionText")}
              </p>
            </div>
          </div>
          <div className="space-y-2 pt-4 border-t border-border">
            {detailRows.map((row) => (
              <div key={row.label} className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{row.label}</span>
                <span className="font-medium">{row.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Features list */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="font-medium mb-4">{t("settings.aboutSection.features")}</h3>
          <ul className="space-y-2">
            {ABOUT_FEATURE_KEYS.map((key) => (
              <li key={key} className="flex items-start gap-2 text-sm text-muted-foreground">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-muted-foreground flex-shrink-0" />
                <span>{t(key)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
