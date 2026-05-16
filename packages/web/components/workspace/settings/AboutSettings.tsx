"use client";

import { BookOpen } from "lucide-react";
import { useTranslations } from "next-intl";

const FEATURES = [
  "feature1",
  "feature2",
  "feature3",
  "feature4",
  "feature5",
] as const;

export function AboutSettings() {
  const t = useTranslations("settings");

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl mb-2">{t("about")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("aboutDescription")}
        </p>
      </div>

      <div className="space-y-4">
        {/* App info card */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
              <BookOpen className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h3 className="mb-1 font-medium">{t("appName")}</h3>
              <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
                {t("appDescription")}
              </p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t("version")}</span>
                  <span className="font-medium">1.0.0</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t("license")}</span>
                  <span className="font-medium">MIT</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t("build")}</span>
                  <span className="font-medium">2024.05.15</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Features card */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="font-medium mb-3">{t("features")}</h3>
          <ul className="space-y-2 text-sm">
            {FEATURES.map((featureKey) => (
              <li key={featureKey} className="flex items-start gap-2">
                <span className="text-foreground mt-0.5">•</span>
                <span>{t(featureKey)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
